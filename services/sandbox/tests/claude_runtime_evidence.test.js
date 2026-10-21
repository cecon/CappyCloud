'use strict'
//   node --test services/sandbox/tests/claude_runtime_evidence.test.js
const test = require('node:test')
const assert = require('node:assert/strict')

const { evidenceServer } = require('../claude_runtime_setup')

test('servidor cappy leva o contexto da conversa para o MCP', () => {
  const context = { repos: [{ slug: 'seller' }], session_root: '/repos/workspaces/loja/sessions/abc' }
  const { cappy } = evidenceServer(context)
  assert.equal(cappy.type, 'stdio')
  assert.equal(cappy.command, 'python3')
  assert.equal(cappy.alwaysLoad, true)
  assert.match(cappy.args[0], /evidence_mcp_server\.py$/)
  assert.deepEqual(JSON.parse(cappy.env.CAPPY_TOOL_CONTEXT), context)
  assert.ok(cappy.env.PYTHONPATH)
})

test('sem contexto (API antiga ou openclaude) não registra o servidor', () => {
  assert.deepEqual(evidenceServer(undefined), {})
  assert.deepEqual(evidenceServer('x'), {})
})
