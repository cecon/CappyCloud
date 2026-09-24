'use strict'
// Runtime alternativo do agente: Claude Code oficial via Claude Agent SDK.
//
//   POST /claude/turns              → executa um turno; resposta NDJSON com os
//                                     mesmos eventos que o openclaude emite via gRPC
//   POST /claude/turns/:id/input    → responde um action_required pendente
//   POST /claude/turns/:id/cancel   → aborta o turno
//   GET  /claude/status             → CLI instalado? versão? credencial do `claude login`?
//
// Todos exigem o header X-Internal-Token = INTERNAL_API_TOKEN (rede interna do stack).
// A autenticação do modelo é a do `claude login` feito no terminal do sandbox;
// as credenciais ficam em CLAUDE_CONFIG_DIR (volume persistente).

const crypto = require('crypto')
const fs = require('fs')
const path = require('path')
const { execFileSync } = require('child_process')
const { pathToFileURL } = require('url')

const {
  createEventMapper,
  friendlyError,
  isYesReply,
  modelAlias,
  sdkPermissionMode,
  userContentBlocks,
  validateToolScope,
  workspaceReadOnlyDirs,
} = require('./claude_runtime_mapper')

const CONFIG_DIR = process.env.CLAUDE_CONFIG_DIR || path.join(process.env.HOME || '/root', '.claude')
const SESSIONS_FILE = path.join(CONFIG_DIR, 'cappycloud-sessions.json')
const OPENCLAUDE_CONFIG = path.join(process.env.HOME || '/root', '.openclaude.json')
// Variáveis do openclaude (provider OpenAI-compatível) que não podem vazar para o CLI oficial.
const STRIPPED_ENV = /^(OPENAI_|CLAUDE_CODE_USE_OPENAI$|CLAUDE_CODE_PROVIDER_PROFILE_ENV_APPLIED$)/

const turns = new Map()
let sdkPromise = null

const SDK_PACKAGE = '@anthropic-ai/claude-agent-sdk'

/**
 * Caminho do entrypoint ESM do SDK instalado globalmente. Nem import() nem
 * require.resolve() acham o pacote via NODE_PATH (o `exports` dele só expõe a
 * condição `default` para .mjs), então procuramos o package.json nas raízes globais.
 */
function sdkEntry() {
  const roots = [...(process.env.NODE_PATH || '').split(path.delimiter), '/usr/local/lib/node_modules']
  for (const root of roots.filter(Boolean)) {
    const pkgDir = path.join(root, SDK_PACKAGE)
    const pkg = readJson(path.join(pkgDir, 'package.json'), null)
    if (!pkg) continue
    const exported = pkg.exports && pkg.exports['.']
    const target = (exported && (exported.import || exported.default)) || pkg.main || 'sdk.mjs'
    return path.join(pkgDir, target)
  }
  throw new Error(`${SDK_PACKAGE} não está instalado no sandbox`)
}

function loadSdk() {
  if (!sdkPromise) {
    sdkPromise = import(pathToFileURL(sdkEntry()).href)
    sdkPromise.catch(() => { sdkPromise = null })
  }
  return sdkPromise
}

function claudeExecutable() {
  try {
    return execFileSync('sh', ['-c', 'command -v claude'], { encoding: 'utf8' }).trim() || null
  } catch {
    return null
  }
}

function readJson(file, fallback) {
  try { return JSON.parse(fs.readFileSync(file, 'utf8')) } catch { return fallback }
}

// Valor por conversa: { session_id, totals } (antes era só o id da sessão).
function storedSession(conversationKey) {
  const raw = conversationKey ? readJson(SESSIONS_FILE, {})[conversationKey] : null
  if (!raw) return { sessionId: null, totals: null }
  if (typeof raw === 'string') return { sessionId: raw, totals: null }
  return { sessionId: raw.session_id || null, totals: raw.totals || null }
}

function rememberSession(conversationKey, sessionId, totals = null) {
  if (!conversationKey) return
  const sessions = readJson(SESSIONS_FILE, {})
  if (sessionId) sessions[conversationKey] = { session_id: sessionId, totals }
  else delete sessions[conversationKey]
  fs.mkdirSync(CONFIG_DIR, { recursive: true })
  fs.writeFileSync(SESSIONS_FILE, JSON.stringify(sessions, null, 2), 'utf8')
}

function sdkEnv() {
  const env = {}
  for (const [key, value] of Object.entries(process.env)) {
    if (!STRIPPED_ENV.test(key)) env[key] = value
  }
  env.CLAUDE_CONFIG_DIR = CONFIG_DIR
  env.IS_SANDBOX = '1'
  // A sessão acaba com o turno: subagente/Bash em segundo plano morreria sem
  // entregar o resultado ("aguarde um instante" e nada mais). Tudo roda no turno.
  env.CLAUDE_CODE_DISABLE_BACKGROUND_TASKS = '1'
  return env
}

function authorized(req) {
  const expected = process.env.INTERNAL_API_TOKEN || ''
  const given = String(req.headers['x-internal-token'] || '')
  if (!expected || given.length !== expected.length) return false
  return crypto.timingSafeEqual(Buffer.from(given), Buffer.from(expected))
}

function claudeStatus() {
  const executable = claudeExecutable()
  let version = null
  if (executable) {
    try { version = execFileSync(executable, ['--version'], { encoding: 'utf8', timeout: 15_000 }).trim() } catch {}
  }
  let sdkInstalled = true
  try { sdkEntry() } catch { sdkInstalled = false }
  return {
    installed: !!executable && sdkInstalled,
    sdk_installed: sdkInstalled,
    version,
    logged_in: fs.existsSync(path.join(CONFIG_DIR, '.credentials.json')),
    config_dir: CONFIG_DIR,
    active_turns: turns.size,
  }
}

/** Uma mensagem de utilizador como stream que só fecha quando o turno termina. */
async function* promptStream(content, finished) {
  yield { type: 'user', message: { role: 'user', content }, parent_tool_use_id: null }
  await finished
}

async function runTurn(body, write, turn) {
  const executable = claudeExecutable()
  if (!executable) {
    write({ type: 'error', message: 'Claude CLI não está instalado neste sandbox.' })
    return
  }
  const { query } = await loadSdk()
  const worktree = body.cwd || '/repos'
  const { alias, known } = modelAlias(body.model)
  if (!known && body.model) {
    write({
      type: 'status',
      message: `Modelo ${body.model} não é Claude; o Claude CLI vai usar ${alias}.`,
    })
  }

  const mcpServers = readJson(OPENCLAUDE_CONFIG, {}).mcpServers || {}
  const mode = sdkPermissionMode(body.permission_mode)
  const content = userContentBlocks(body.prompt, body.attachments)

  const stored = storedSession(body.conversation_key)
  const attempt = async (resume) => {
    let resolveFinished
    const finished = new Promise((resolve) => { resolveFinished = resolve })
    // Totais da sessão retomada: o done informa só o consumo deste turno.
    const mapper = createEventMapper({ requestedModel: alias, previousTotals: resume ? stored.totals : null })
    let emitted = 0

    const canUseTool = (toolName, input, { signal }) =>
      askUser(turn, write, toolName, input, signal)

    const stream = query({
      prompt: promptStream(content, finished),
      options: {
        abortController: turn.abort,
        cwd: worktree,
        // Sessão de workspace: leitura do conhecimento/skills/repos somente leitura (o guard barra escrita).
        additionalDirectories: workspaceReadOnlyDirs(worktree),
        model: alias,
        permissionMode: mode,
        allowDangerouslySkipPermissions: mode === 'bypassPermissions',
        // Em bypassPermissions o SDK aprova tudo antes do callback; só registra quando pode perguntar.
        ...(mode === 'bypassPermissions' ? {} : { canUseTool }),
        hooks: {
          PreToolUse: [{
            hooks: [async (input) => {
              const reason = validateToolScope(input.tool_name, input.tool_input, worktree)
              if (!reason) return {}
              return {
                hookSpecificOutput: {
                  hookEventName: 'PreToolUse',
                  permissionDecision: 'deny',
                  permissionDecisionReason: reason,
                },
              }
            }],
          }],
        },
        mcpServers,
        settingSources: ['user', 'project'],
        systemPrompt: { type: 'preset', preset: 'claude_code' },
        includePartialMessages: true,
        pathToClaudeCodeExecutable: executable,
        env: sdkEnv(),
        stderr: (data) => console.error(`[claude_runtime] ${String(data).trimEnd()}`),
        ...(resume ? { resume } : {}),
      },
    })

    try {
      for await (const message of stream) {
        for (const event of mapper.map(message)) {
          emitted += 1
          write(event)
        }
        if (message.type === 'result') break
      }
    } finally {
      resolveFinished()
    }
    return { emitted, sessionId: mapper.getSessionId(), totals: mapper.getTotals() }
  }

  const resume = stored.sessionId
  let outcome
  try {
    outcome = await attempt(resume)
  } catch (err) {
    // Sessão guardada pode ter sumido (volume limpo, cwd diferente): tenta sem resume.
    if (resume && !turn.abort.signal.aborted) {
      console.error('[claude_runtime] resume falhou, recomeçando sessão:', err.message)
      rememberSession(body.conversation_key, null)
      outcome = await attempt(null)
    } else {
      throw err
    }
  }
  if (outcome.sessionId) rememberSession(body.conversation_key, outcome.sessionId, outcome.totals)
}

/** Converte um pedido de permissão (ou AskUserQuestion) em action_required e espera a resposta. */
function askUser(turn, write, toolName, input, signal) {
  const promptId = crypto.randomUUID()
  const questions = toolName === 'AskUserQuestion' && Array.isArray(input.questions) ? input.questions : null
  const first = questions && questions[0]
  write({
    type: 'action_required',
    prompt_id: promptId,
    question: first ? String(first.question || '') : `Aprovar ${toolName}?\n${JSON.stringify(input).slice(0, 400)}`,
    action_type: first ? 2 : 1,
    choices: first
      ? (first.options || []).map((option) => String(option.label || option)).filter(Boolean)
      : ['sim', 'não'],
  })

  return new Promise((resolve) => {
    const settle = (reply) => {
      turn.pending.delete(promptId)
      if (first) {
        resolve({ behavior: 'allow', updatedInput: { ...input, answers: { [first.question]: reply } } })
      } else if (isYesReply(reply)) {
        resolve({ behavior: 'allow', updatedInput: input })
      } else {
        resolve({ behavior: 'deny', message: `O utilizador negou ${toolName}.` })
      }
    }
    turn.pending.set(promptId, settle)
    signal.addEventListener('abort', () => {
      turn.pending.delete(promptId)
      resolve({ behavior: 'deny', message: 'Turno cancelado.', interrupt: true })
    }, { once: true })
  })
}

async function handleTurn(req, res, readBody) {
  const body = await readBody(req)
  const turnId = String(body.turn_id || crypto.randomUUID())
  const turn = { abort: new AbortController(), pending: new Map() }
  turns.set(turnId, turn)

  res.writeHead(200, { 'Content-Type': 'application/x-ndjson', 'Cache-Control': 'no-cache' })
  const write = (event) => {
    if (!res.writableEnded) res.write(`${JSON.stringify(event)}\n`)
  }
  // Cliente caiu (backend reiniciou/cancelou): não deixa o agente rodando sozinho.
  res.on('close', () => { if (!res.writableFinished) turn.abort.abort() })

  try {
    await runTurn(body, write, turn)
  } catch (err) {
    if (!turn.abort.signal.aborted) {
      console.error('[claude_runtime] turno falhou:', err)
      write({ type: 'error', message: friendlyError(err.message) })
    }
  } finally {
    turns.delete(turnId)
    res.end()
  }
}

async function tryHandle(req, res, { json, readBody }) {
  const pathname = (req.url || '').split('?')[0]
  if (!pathname.startsWith('/claude/')) return false
  if (!authorized(req)) {
    json(res, 401, { error: 'unauthorized' })
    return true
  }

  if (req.method === 'GET' && pathname === '/claude/status') {
    json(res, 200, claudeStatus())
    return true
  }
  if (req.method === 'POST' && pathname === '/claude/turns') {
    await handleTurn(req, res, readBody)
    return true
  }

  const match = pathname.match(/^\/claude\/turns\/([^/]+)\/(input|cancel)$/)
  if (req.method === 'POST' && match) {
    const turn = turns.get(match[1])
    if (!turn) {
      json(res, 404, { error: 'turn not found' })
      return true
    }
    if (match[2] === 'cancel') {
      turn.abort.abort()
      json(res, 202, { canceled: true })
      return true
    }
    const body = await readBody(req)
    const settle = turn.pending.get(String(body.prompt_id || ''))
    if (!settle) {
      json(res, 409, { error: 'no pending prompt' })
      return true
    }
    settle(String(body.reply || ''))
    json(res, 200, { accepted: true })
    return true
  }

  json(res, 404, { error: 'Not found' })
  return true
}

module.exports = { tryHandle, claudeStatus }
