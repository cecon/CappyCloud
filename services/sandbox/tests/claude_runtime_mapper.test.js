'use strict'
// node --test services/sandbox/tests/claude_runtime_mapper.test.js
const test = require('node:test')
const assert = require('node:assert/strict')

const {
  LOGIN_HINT,
  createEventMapper,
  friendlyError,
  isYesReply,
  modelAlias,
  sdkPermissionMode,
  userContentBlocks,
  validateToolScope,
  planUsageFrom,
  workspaceReadOnlyDirs,
} = require('../claude_runtime_mapper')

const WORKTREE = '/repos/sessions/abc/seller'

test('mapeia modos de permissão do CappyCloud para o SDK', () => {
  assert.equal(sdkPermissionMode('request_permissions'), 'default')
  assert.equal(sdkPermissionMode('accept_edits'), 'acceptEdits')
  assert.equal(sdkPermissionMode('plan'), 'plan')
  assert.equal(sdkPermissionMode('auto'), 'bypassPermissions')
  assert.equal(sdkPermissionMode('desconhecido'), 'bypassPermissions')
})

test('converte ids do catálogo em alias do Claude CLI', () => {
  assert.deepEqual(modelAlias('anthropic/claude-opus-4.1'), { alias: 'opus', known: true })
  assert.deepEqual(modelAlias('anthropic/claude-3.5-haiku'), { alias: 'haiku', known: true })
  assert.deepEqual(modelAlias('anthropic/claude-sonnet-4.5'), { alias: 'sonnet', known: true })
  assert.deepEqual(modelAlias('deepseek/deepseek-v4'), { alias: 'sonnet', known: false })
})

test('aceita respostas afirmativas em português e inglês', () => {
  for (const reply of ['sim', 'S', ' yes ', 'y']) assert.equal(isYesReply(reply), true)
  for (const reply of ['não', 'no', '']) assert.equal(isYesReply(reply), false)
})

test('bloqueia caminhos e comandos fora do worktree', () => {
  assert.equal(validateToolScope('Read', { file_path: 'src/app.py' }, WORKTREE), null)
  assert.match(validateToolScope('Read', { file_path: '/etc/passwd' }, WORKTREE), /outside the conversation worktree/)
  assert.match(validateToolScope('Bash', { command: 'cd .. && ls' }, WORKTREE), /leave the conversation worktree/)
  assert.match(
    validateToolScope('Bash', { command: 'cat /repos/sessions/outra/x.txt' }, WORKTREE),
    /repo path outside/,
  )
  assert.equal(validateToolScope('Bash', { command: 'git status' }, WORKTREE), null)
})

test('monta imagens em base64 antes do texto', () => {
  const blocks = userContentBlocks('olá', [
    { mime_type: 'image/png', data_base64: 'AAAA' },
    { mime_type: 'application/pdf', data_base64: 'BBBB' },
  ])
  assert.deepEqual(blocks.map((b) => b.type), ['image', 'text'])
  assert.equal(blocks[0].source.media_type, 'image/png')
})

test('traduz um turno completo do SDK para eventos do CappyCloud', () => {
  const mapper = createEventMapper({ requestedModel: 'sonnet' })
  const events = [
    { type: 'system', subtype: 'init', model: 'claude-sonnet-5', session_id: 's-1' },
    { type: 'stream_event', parent_tool_use_id: null, event: { type: 'message_start', message: { id: 'm1' } } },
    { type: 'stream_event', parent_tool_use_id: null, event: { type: 'content_block_delta', delta: { type: 'text_delta', text: 'Vou ler.' } } },
    {
      type: 'assistant',
      parent_tool_use_id: null,
      message: { id: 'm1', content: [
        { type: 'text', text: 'Vou ler.' },
        { type: 'tool_use', id: 't1', name: 'Read', input: { file_path: 'a.py' } },
      ] },
    },
    {
      type: 'user',
      message: { content: [{ type: 'tool_result', tool_use_id: 't1', content: [{ type: 'text', text: 'print(1)' }] }] },
    },
    {
      type: 'result',
      subtype: 'success',
      is_error: false,
      result: 'Vou ler.',
      modelUsage: { 'claude-sonnet-5': { inputTokens: 10, cacheReadInputTokens: 5, cacheCreationInputTokens: 0, outputTokens: 7 } },
    },
  ].flatMap((message) => mapper.map(message))

  assert.deepEqual(events.map((e) => e.type), ['text', 'tool_start', 'tool_result', 'done'])
  assert.equal(events[1].input, '{"file_path":"a.py"}')
  assert.deepEqual(events[2], { type: 'tool_result', name: 'Read', output: 'print(1)', is_error: false, id: 't1' })
  assert.deepEqual(events[3], { type: 'done', prompt_tokens: 15, completion_tokens: 7, model_used: 'claude-sonnet-5' })
  assert.equal(mapper.getSessionId(), 's-1')
})

test('usa o texto do resultado quando nada foi transmitido e reporta erros', () => {
  const ok = createEventMapper().map({ type: 'result', subtype: 'success', is_error: false, result: 'oi', modelUsage: {} })
  assert.deepEqual(ok.map((e) => e.type), ['text', 'done'])

  const failed = createEventMapper().map({ type: 'result', subtype: 'error_during_execution', is_error: true, errors: ['boom'] })
  assert.deepEqual(failed, [{ type: 'error', message: 'Claude CLI: boom' }])
})

test('subagente vira um cartão próprio: ferramentas dele não se misturam às do agente', () => {
  const mapper = createEventMapper()
  const main = mapper.map({
    type: 'assistant',
    message: { id: 'm1', content: [
      { type: 'tool_use', id: 'ag1', name: 'Agent', input: { description: 'Buscar versão do schema Realm', prompt: '...' } },
    ] },
  })
  assert.deepEqual(main.map((e) => e.type), ['tool_start', 'subagent_group'])
  assert.equal(main[1].label, 'Subagente · Buscar versão do schema Realm')
  assert.equal(main[1].activities[0].state, 'loading')

  const inside = mapper.map({
    type: 'assistant',
    parent_tool_use_id: 'ag1',
    message: { id: 'm2', content: [
      { type: 'text', text: 'interno' },
      { type: 'tool_use', id: 't9', name: 'Bash', input: { command: 'rg -n schemaVersion src', description: 'Busca schemaVersion' } },
    ] },
  })
  assert.deepEqual(inside.map((e) => e.type), ['subagent_group'])
  assert.deepEqual(inside[0].activities[1], { id: 't9', name: 'Bash', state: 'tool-running', detail: 'Busca schemaVersion' })

  const toolDone = mapper.map({
    type: 'user',
    parent_tool_use_id: 'ag1',
    message: { content: [{ type: 'tool_result', tool_use_id: 't9', content: 'src/db.js:3: schemaVersion: 42' }] },
  })
  assert.deepEqual(toolDone.map((e) => e.type), ['subagent_group'])
  assert.equal(toolDone[0].activities[1].state, 'done')

  const finished = mapper.map({
    type: 'user',
    message: { content: [{ type: 'tool_result', tool_use_id: 'ag1', content: [{ type: 'text', text: 'schemaVersion 42' }] }] },
  })
  assert.deepEqual(finished.map((e) => e.type), ['tool_result', 'subagent_group'])
  assert.equal(finished[1].activities[0].state, 'done')
  assert.ok(finished[1].activities.every((activity) => activity.state === 'done'))
})

test('sem login vira só um erro com a instrução do terminal', () => {
  const mapper = createEventMapper()
  const events = [
    {
      type: 'assistant',
      parent_tool_use_id: null,
      error: 'authentication_failed',
      message: { id: 'm3', content: [{ type: 'text', text: 'Not logged in · Please run /login' }] },
    },
    { type: 'result', subtype: 'success', is_error: true, result: 'Not logged in · Please run /login' },
  ].flatMap((message) => mapper.map(message))

  assert.deepEqual(events, [{ type: 'error', message: LOGIN_HINT }])
  assert.equal(friendlyError('boom'), 'Claude CLI: boom')
})

test('sessão de workspace: leitura do compartilhado, escrita e Bash só no worktree', () => {
  const session = '/repos/workspaces/loja/sessions/abc'
  assert.deepEqual(workspaceReadOnlyDirs(session), [
    '/repos/workspaces/loja/knowledge',
    '/repos/workspaces/loja/memory',
    '/repos/workspaces/loja/.claude',
    '/repos/workspaces/loja/repos',
  ])
  assert.deepEqual(workspaceReadOnlyDirs('/repos/sessions/abc'), [])
  for (const file of ['knowledge/x.md', 'repos/docs/README.md', 'CLAUDE.md']) {
    const target = `/repos/workspaces/loja/${file}`
    assert.equal(validateToolScope('Read', { file_path: target }, session), null, file)
  }
  assert.equal(validateToolScope('Grep', { path: '/repos/workspaces/loja/repos/docs' }, session), null)
  assert.match(
    validateToolScope('Edit', { file_path: '/repos/workspaces/loja/repos/docs/a.md' }, session),
    /outside the conversation worktree/,
  )
  // Bash só de leitura no repo somente leitura passa (não há Grep/Glob no Claude Code); escrita não.
  assert.equal(validateToolScope('Bash', { command: 'cat /repos/workspaces/loja/repos/docs/a.md' }, session), null)
  assert.match(
    validateToolScope('Bash', { command: 'echo x > /repos/workspaces/loja/repos/docs/a.md' }, session),
    /outside the conversation worktree/,
  )
  assert.match(
    validateToolScope('Read', { file_path: '/repos/workspaces/outra/knowledge/x.md' }, session),
    /outside the conversation worktree/,
  )
})

test('modelo usado é o principal, não o auxiliar que aparece primeiro', () => {
  const usage = {
    'claude-haiku-4-5-20251001': { inputTokens: 900, outputTokens: 40 },
    'claude-sonnet-5': { inputTokens: 50, outputTokens: 800 },
  }
  const result = { type: 'result', subtype: 'success', is_error: false, result: 'ok', modelUsage: usage }
  const withInit = createEventMapper()
  withInit.map({ type: 'system', subtype: 'init', session_id: 's', model: 'claude-sonnet-5' })
  assert.equal(withInit.map(result).at(-1).model_used, 'claude-sonnet-5')
  // Sem o init: o que mais gerou texto.
  assert.equal(createEventMapper().map(result).at(-1).model_used, 'claude-sonnet-5')
})

test('uso da assinatura: janelas de 5h e 7 dias vão no done', () => {
  const mapper = createEventMapper()
  mapper.map({
    type: 'rate_limit_event',
    rate_limit_info: {
      status: 'allowed',
      rateLimitType: 'five_hour',
      resetsAt: 1790260200,
      unifiedWindows: {
        five_hour: { utilization: 0.12, resetsAt: 1790260200 },
        seven_day: { utilization: 0.07, resetsAt: 1790812800 },
      },
    },
  })
  const done = mapper.map({
    type: 'result', subtype: 'success', is_error: false, result: 'ok', modelUsage: {}, total_cost_usd: 0.5432,
  }).at(-1)
  assert.equal(done.cost_usd, 0.5432)
  assert.deepEqual(done.plan_usage, {
    status: 'allowed',
    five_hour: { used_pct: 12, resets_at: '2026-09-24T14:30:00.000Z' },
    seven_day: { used_pct: 7, resets_at: '2026-10-01T00:00:00.000Z' },
  })
})

test('sem evento de limite (API key) o done não traz plan_usage', () => {
  const mapper = createEventMapper()
  const done = mapper.map({ type: 'result', subtype: 'success', is_error: false, result: 'ok', modelUsage: {} }).at(-1)
  assert.equal('plan_usage' in done, false)
  assert.equal(planUsageFrom({ status: 'allowed' }), null)
})

test('sessão retomada: tokens e custo do turno, não o acumulado da sessão', () => {
  // Números medidos no Claude Code: 2º turno com --resume soma o 1º.
  const usage = { 'claude-haiku-4-5': { inputTokens: 20, cacheReadInputTokens: 39630, cacheCreationInputTokens: 3732, outputTokens: 130 } }
  const result = { type: 'result', subtype: 'success', is_error: false, result: 'DOIS', modelUsage: usage, total_cost_usd: 0.0121 }
  const previousTotals = { prompt_tokens: 21625, completion_tokens: 86, cost_usd: 0.00944 }
  const mapper = createEventMapper({ previousTotals })
  const done = mapper.map(result).at(-1)
  assert.equal(done.prompt_tokens, 43382 - 21625)
  assert.equal(done.completion_tokens, 44)
  assert.equal(done.cost_usd, 0.00266)
  assert.deepEqual(mapper.getTotals(), { prompt_tokens: 43382, completion_tokens: 130, cost_usd: 0.0121 })
  // Sem totais anteriores (sessão nova): o próprio total.
  assert.equal(createEventMapper().map(result).at(-1).prompt_tokens, 43382)
})

test('lista os subagentes gravados em ~/.claude/agents', () => {
  const fs = require('fs')
  const os = require('os')
  const path = require('path')
  const { agentNames } = require('../claude_runtime_subagents')
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'cappy-agents-'))
  fs.writeFileSync(path.join(dir, 'seller-architect.md'), '---\nname: seller-architect\n---\n')
  fs.writeFileSync(path.join(dir, 'notas.txt'), '')
  assert.deepEqual(agentNames(dir), ['seller-architect'])
  assert.deepEqual(agentNames(path.join(dir, 'nao-existe')), [])
})
