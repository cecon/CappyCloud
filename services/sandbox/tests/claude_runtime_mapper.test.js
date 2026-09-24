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

test('ignora texto de subagentes mas mostra suas ferramentas', () => {
  const mapper = createEventMapper()
  const events = mapper.map({
    type: 'assistant',
    parent_tool_use_id: 'task-1',
    message: { id: 'm2', content: [
      { type: 'text', text: 'interno' },
      { type: 'tool_use', id: 't9', name: 'Grep', input: { pattern: 'x' } },
    ] },
  })
  assert.deepEqual(events.map((e) => e.type), ['tool_start'])
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
  assert.match(
    validateToolScope('Bash', { command: 'cat /repos/workspaces/loja/repos/docs/a.md' }, session),
    /outside the conversation worktree/,
  )
  assert.match(
    validateToolScope('Read', { file_path: '/repos/workspaces/outra/knowledge/x.md' }, session),
    /outside the conversation worktree/,
  )
})
