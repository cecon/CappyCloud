'use strict'
// Funções puras do runtime Claude CLI (Agent SDK): traduzem mensagens do SDK
// para os mesmos eventos que o openclaude emite via gRPC, e replicam o guard
// de escopo do worktree. Sem I/O — testadas com `node --test`.

const path = require('path').posix

/** Modos do CappyCloud → permissionMode do Agent SDK. */
const PERMISSION_MODES = {
  bypass_permissions: 'bypassPermissions',
  auto: 'bypassPermissions',
  accept_edits: 'acceptEdits',
  plan: 'plan',
  request_permissions: 'default',
}

const YES_REPLIES = new Set(['sim', 's', 'yes', 'y'])

// Mesmo conjunto do guard do openclaude (cappycloud_grpc_helpers_v024.ts).
const PATH_GUARDED_TOOLS = new Set([
  'Read', 'Write', 'Edit', 'Grep', 'Glob', 'NotebookEdit', 'LSP', 'SendUserMessage', 'Brief',
])
const COMMAND_GUARDED_TOOLS = new Set(['Bash', 'Monitor'])
const PATH_INPUT_KEYS = ['file_path', 'path', 'notebook_path']
const READ_ONLY_TOOLS = new Set(['Read', 'Grep', 'Glob', 'LSP'])
const WORKSPACE_SESSION_RE = /^(\/repos\/workspaces\/[a-z0-9][a-z0-9-]{1,62})\/sessions\/[^/]+$/
const WORKSPACE_SHARED_DIRS = ['knowledge', 'memory', '.claude', 'repos']

/** Pastas do workspace que a sessão lê (conhecimento, skills, repos somente leitura). */
function workspaceReadOnlyDirs(worktree) {
  const match = path.resolve(worktree || '/').match(WORKSPACE_SESSION_RE)
  return match ? WORKSPACE_SHARED_DIRS.map((dir) => `${match[1]}/${dir}`) : []
}

function workspaceReadOnlyRoots(worktree) {
  const dirs = workspaceReadOnlyDirs(worktree)
  return dirs.length ? [...dirs, `${path.dirname(dirs[0])}/CLAUDE.md`] : []
}

function sdkPermissionMode(mode) {
  return PERMISSION_MODES[mode] || 'bypassPermissions'
}

function isYesReply(reply) {
  return YES_REPLIES.has(String(reply || '').trim().toLowerCase())
}

/**
 * Converte o id de modelo do catálogo (ex.: "anthropic/claude-sonnet-4.5")
 * no alias aceito pelo Claude CLI. Modelos não-Claude caem no padrão.
 */
function modelAlias(modelId) {
  const id = String(modelId || '').toLowerCase()
  if (id.includes('opus')) return { alias: 'opus', known: true }
  if (id.includes('haiku')) return { alias: 'haiku', known: true }
  if (id.includes('sonnet')) return { alias: 'sonnet', known: true }
  return { alias: 'sonnet', known: id.includes('claude') }
}

function isInsideWorktree(worktree, candidate) {
  const relative = path.relative(worktree, candidate)
  return relative === '' || (!!relative && !relative.startsWith('..') && !path.isAbsolute(relative))
}

function resolveToolPath(worktree, rawPath) {
  const cleaned = String(rawPath).trim()
  if (!cleaned || cleaned === '.' || cleaned === 'undefined' || cleaned === 'null') return null
  if (/^[a-zA-Z][a-zA-Z0-9+.-]*:\/\//.test(cleaned)) return null
  return path.resolve(path.isAbsolute(cleaned) ? cleaned : path.join(worktree, cleaned))
}

function extractRepoPaths(command) {
  const paths = []
  for (const match of command.matchAll(/(?:^|[\s"'=:(])((?:\/repos\/)[^\s"'`;&|)<>]+)/g)) {
    const rawPath = match[1] && match[1].replace(/[.,:]+$/g, '')
    if (rawPath) paths.push(rawPath)
  }
  return paths
}

/** Devolve a mensagem de bloqueio quando a ferramenta sai do worktree, ou null. */
function validateToolScope(toolName, input, worktree) {
  if (!worktree || !input || typeof input !== 'object') return null
  const readOnlyRoots = READ_ONLY_TOOLS.has(toolName) ? workspaceReadOnlyRoots(worktree) : []
  if (PATH_GUARDED_TOOLS.has(toolName)) {
    for (const key of PATH_INPUT_KEYS) {
      if (typeof input[key] !== 'string') continue
      const resolved = resolveToolPath(worktree, input[key])
      if (resolved && readOnlyRoots.some((root) => isInsideWorktree(root, resolved))) continue
      if (resolved && !isInsideWorktree(worktree, resolved)) {
        return `Tool blocked: path outside the conversation worktree. Allowed worktree: ${worktree}. Requested path: ${resolved}.`
      }
    }
  }
  if (COMMAND_GUARDED_TOOLS.has(toolName) && typeof input.command === 'string') {
    const command = input.command
    if (/(^|[\s;&|])cd\s+\.\.(?:\/|\s|$)/.test(command) || /(^|[\s"'=])\.\.(?:\/|$)/.test(command)) {
      return `Tool blocked: command tries to leave the conversation worktree. Allowed worktree: ${worktree}.`
    }
    for (const rawPath of extractRepoPaths(command)) {
      const resolved = resolveToolPath(worktree, rawPath)
      if (resolved && !isInsideWorktree(worktree, resolved)) {
        return `Tool blocked: command references a repo path outside the conversation worktree. Allowed worktree: ${worktree}. Requested path: ${resolved}.`
      }
    }
  }
  return null
}

/** Monta o conteúdo da mensagem do utilizador (texto + imagens em base64). */
function userContentBlocks(prompt, attachments) {
  const blocks = []
  for (const attachment of attachments || []) {
    const mime = String(attachment.mime_type || '')
    if (!mime.startsWith('image/') || !attachment.data_base64) continue
    blocks.push({
      type: 'image',
      source: { type: 'base64', media_type: mime, data: attachment.data_base64 },
    })
  }
  blocks.push({ type: 'text', text: String(prompt || '') })
  return blocks
}

function toolResultText(content) {
  if (typeof content === 'string') return content
  if (!Array.isArray(content)) return content == null ? '' : JSON.stringify(content)
  return content
    .map((block) => (block && block.type === 'text' ? block.text : block && block.type ? `[${block.type}]` : ''))
    .filter(Boolean)
    .join('\n')
}

const LOGIN_HINT =
  'Claude CLI sem login nesta sandbox. Rode `claude login` no terminal do sandbox ' +
  '(Dokploy → Docker → cappycloud_sandbox → Terminal) e tente de novo.'

/** Mensagem de erro amigável para falhas conhecidas do Claude CLI. */
function friendlyError(detail) {
  const text = String(detail || '')
  if (/not logged in|please run \/login|invalid api key|oauth token/i.test(text)) return LOGIN_HINT
  return `Claude CLI: ${text}`
}

/**
 * Modelo principal do turno. O Claude Code também gasta tokens com modelos
 * auxiliares (ex.: Haiku para tarefas internas), então a primeira chave de
 * `modelUsage` nem sempre é o modelo que respondeu.
 */
function mainModel(modelUsage, initModel) {
  const usage = modelUsage || {}
  if (initModel && usage[initModel]) return initModel
  let best = ''
  let bestOutput = -1
  for (const [model, item] of Object.entries(usage)) {
    if ((item.outputTokens || 0) > bestOutput) {
      best = model
      bestOutput = item.outputTokens || 0
    }
  }
  return best || initModel
}

/** Fração (0-1, como o Claude Code manda) ou percentual → percentual com 1 casa. */
function toPercent(value) {
  if (typeof value !== 'number' || !Number.isFinite(value)) return null
  const pct = value <= 1 ? value * 100 : value
  return Math.round(Math.min(Math.max(pct, 0), 100) * 10) / 10
}

/**
 * Uso da assinatura (`claude login`) a partir do `rate_limit_event`: quanto
 * das janelas de 5 horas e 7 dias já foi usado e quando cada uma renova.
 */
function planUsageFrom(info) {
  if (!info || typeof info !== 'object') return null
  const windows = { ...(info.unifiedWindows || {}) }
  if (info.rateLimitType && !windows[info.rateLimitType]) {
    windows[info.rateLimitType] = { utilization: info.utilization, resetsAt: info.resetsAt }
  }
  const usage = { status: info.status || null }
  for (const name of ['five_hour', 'seven_day']) {
    const window = windows[name]
    if (!window) continue
    const resetsAt = Number(window.resetsAt)
    usage[name] = {
      used_pct: toPercent(window.utilization),
      resets_at: Number.isFinite(resetsAt) && resetsAt > 0 ? new Date(resetsAt * 1000).toISOString() : null,
    }
  }
  return usage.five_hour || usage.seven_day ? usage : null
}

function sumUsage(modelUsage) {
  let promptTokens = 0
  let completionTokens = 0
  for (const usage of Object.values(modelUsage || {})) {
    promptTokens += (usage.inputTokens || 0) + (usage.cacheReadInputTokens || 0) +
      (usage.cacheCreationInputTokens || 0)
    completionTokens += usage.outputTokens || 0
  }
  return { promptTokens, completionTokens }
}

/**
 * Cria um mapeador com estado (um por turno). `map(message)` devolve a lista
 * de eventos CappyCloud correspondentes à mensagem do SDK.
 */
/** Diferença do acumulado; se o total caiu (sessão nova), o próprio total. */
function delta(current, previous) {
  const before = Number(previous) || 0
  return current >= before ? current - before : current
}

/**
 * `modelUsage` e `total_cost_usd` do Claude Code são acumulados da sessão
 * (restaurados no resume). `previousTotals` é o acumulado até o turno anterior;
 * o `done` informa só o que este turno consumiu.
 */
function createEventMapper({ requestedModel = '', previousTotals = null } = {}) {
  const toolNames = new Map()
  const streamedMessages = new Set()
  let currentStreamMessageId = null
  let emittedText = false
  let initModel = ''
  let sessionId = ''
  let planUsage = null
  let totals = null

  function map(message) {
    if (!message || typeof message !== 'object') return []
    if (message.session_id) sessionId = message.session_id

    if (message.type === 'system' && message.subtype === 'init') {
      initModel = message.model || ''
      return []
    }

    if (message.type === 'rate_limit_event') {
      planUsage = planUsageFrom(message.rate_limit_info) || planUsage
      return []
    }

    if (message.type === 'stream_event') {
      const event = message.event || {}
      if (message.parent_tool_use_id) return []
      if (event.type === 'message_start' && event.message) {
        currentStreamMessageId = event.message.id || null
        return []
      }
      if (event.type === 'content_block_delta' && event.delta && event.delta.type === 'text_delta') {
        if (currentStreamMessageId) streamedMessages.add(currentStreamMessageId)
        if (!event.delta.text) return []
        emittedText = true
        return [{ type: 'text', content: event.delta.text }]
      }
      return []
    }

    if (message.type === 'assistant') {
      const events = []
      const inner = message.message || {}
      const streamed = inner.id && streamedMessages.has(inner.id)
      // Mensagens sintéticas de erro (ex.: sem login) viram só o evento de erro do result.
      const synthetic = !!message.error
      for (const block of inner.content || []) {
        if (block.type === 'text' && !message.parent_tool_use_id && !streamed && !synthetic && block.text) {
          emittedText = true
          events.push({ type: 'text', content: block.text })
        } else if (block.type === 'tool_use') {
          toolNames.set(block.id, block.name)
          events.push({
            type: 'tool_start',
            name: block.name,
            input: JSON.stringify(block.input ?? {}),
            id: block.id,
          })
        }
      }
      return events
    }

    if (message.type === 'user') {
      const content = message.message && message.message.content
      if (!Array.isArray(content)) return []
      return content
        .filter((block) => block && block.type === 'tool_result')
        .map((block) => ({
          type: 'tool_result',
          name: toolNames.get(block.tool_use_id) || '',
          output: toolResultText(block.content),
          is_error: block.is_error === true,
          id: block.tool_use_id,
        }))
    }

    if (message.type === 'result') {
      const events = []
      const failed = message.subtype !== 'success' || message.is_error
      if (failed) {
        const detail = message.result || (message.errors || []).join('; ') || message.subtype
        return [{ type: 'error', message: friendlyError(detail) }]
      }
      if (!emittedText && message.result) {
        events.push({ type: 'text', content: message.result })
      }
      const { promptTokens, completionTokens } = sumUsage(message.modelUsage)
      const cost = typeof message.total_cost_usd === 'number' ? message.total_cost_usd : null
      totals = { prompt_tokens: promptTokens, completion_tokens: completionTokens, cost_usd: cost }
      const before = previousTotals || {}
      events.push({
        type: 'done',
        prompt_tokens: delta(promptTokens, before.prompt_tokens),
        completion_tokens: delta(completionTokens, before.completion_tokens),
        model_used: mainModel(message.modelUsage, initModel) || requestedModel,
        // Custo equivalente pela tabela da API da Anthropic (a assinatura não cobra por token).
        ...(cost !== null ? { cost_usd: Math.round(delta(cost, before.cost_usd) * 1e6) / 1e6 } : {}),
        ...(planUsage ? { plan_usage: planUsage } : {}),
      })
      return events
    }

    return []
  }

  return { map, getSessionId: () => sessionId, getTotals: () => totals }
}

module.exports = {
  LOGIN_HINT,
  createEventMapper,
  friendlyError,
  isYesReply,
  modelAlias,
  sdkPermissionMode,
  userContentBlocks,
  planUsageFrom,
  validateToolScope,
  workspaceReadOnlyDirs,
}
