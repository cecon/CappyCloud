'use strict'
//   node --test services/sandbox/tests/memory_handler.test.js
const test = require('node:test')
const assert = require('node:assert/strict')

const { createClient, listMemories, saveMemory, searchMemory } = require('../memory_handler')

/** agentmemory falso: guarda em memória e filtra por agentId como o servidor isolado. */
function fakeAgentmemory() {
  const memories = []
  const calls = []
  const call = async (path, { method = 'GET', body } = {}) => {
    calls.push([method, path, body])
    if (path === '/remember') {
      const memory = { ...body, id: `mem_${memories.length + 1}`, createdAt: `2026-09-2${memories.length}T00:00:00Z` }
      memories.push(memory)
      return { memory, success: true }
    }
    if (path === '/smart-search') {
      const hits = memories.filter((m) => m.agentId === body.agentId && m.content.includes(body.query))
      return { results: [...hits.map((m) => ({ obsId: m.id, score: 0.9 })), { obsId: 'obs_x', score: 0.1 }] }
    }
    if (path.startsWith('/memories/')) return { memory: memories.find((m) => m.id === decodeURIComponent(path.slice(10))) }
    if (path.startsWith('/memories?')) {
      const agentId = new URLSearchParams(path.split('?')[1]).get('agentId')
      return { memories: memories.filter((m) => m.agentId === agentId) }
    }
    throw new Error(`rota inesperada ${path}`)
  }
  return { call, calls, memories }
}

test('grava com agentId e project do workspace', async () => {
  const am = fakeAgentmemory()
  const result = await saveMemory(am.call, { workspace: 'loja', content: ' desconto em ItemVenda ', type: 'bug', concepts: 'desconto, venda' })

  assert.deepEqual(result, { saved: true, id: 'mem_1' })
  assert.deepEqual(am.calls[0][2], {
    content: 'desconto em ItemVenda', type: 'bug', concepts: ['desconto', 'venda'], files: [], project: 'loja', agentId: 'ws-loja',
  })
})

test('busca só devolve memórias do próprio workspace, com conteúdo', async () => {
  const am = fakeAgentmemory()
  await saveMemory(am.call, { workspace: 'loja', content: 'desconto em ItemVenda' })
  await saveMemory(am.call, { workspace: 'outro', content: 'desconto em promoções' })

  const { results } = await searchMemory(am.call, { workspace: 'loja', q: 'desconto' })
  assert.deepEqual(results.map((r) => r.content), ['desconto em ItemVenda'])
  assert.equal(am.calls.find((c) => c[1] === '/smart-search')[2].agentId, 'ws-loja')
})

test('lista do mais recente para o mais antigo e valida entradas', async () => {
  const am = fakeAgentmemory()
  await saveMemory(am.call, { workspace: 'loja', content: 'primeira' })
  await saveMemory(am.call, { workspace: 'loja', content: 'segunda', type: 'inventado' })

  const listed = await listMemories(am.call, 'loja')
  assert.deepEqual(listed.memories.map((m) => [m.content, m.type]), [['segunda', 'fact'], ['primeira', 'fact']])
  await assert.rejects(saveMemory(am.call, { workspace: '../x', content: 'a' }), /workspace inválido/)
  await assert.rejects(saveMemory(am.call, { workspace: 'loja', content: ' ' }), /content é obrigatório/)
  await assert.rejects(searchMemory(am.call, { workspace: 'loja', q: '' }), /q é obrigatório/)
})

test('cliente REST usa o segredo e avisa quando não está configurado', async () => {
  const seen = []
  const call = createClient({
    url: 'http://am:3111/',
    secret: 's3',
    fetchImpl: async (url, init) => {
      seen.push([url, init.headers.Authorization])
      return { ok: true, json: async () => ({ memories: [] }) }
    },
  })
  await call('/memories?agentId=ws-loja')
  assert.deepEqual(seen, [['http://am:3111/agentmemory/memories?agentId=ws-loja', 'Bearer s3']])
  await assert.rejects(createClient({ url: '' })('/x'), /AGENTMEMORY_URL não configurado/)
})
