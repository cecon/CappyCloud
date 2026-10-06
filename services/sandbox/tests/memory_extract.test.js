'use strict'
//   node --test services/sandbox/tests/memory_extract.test.js
const test = require('node:test')
const assert = require('node:assert/strict')

const { buildPrompt, extractAndSave, parseItems } = require('../memory_extract')

function fakeMemory(existing = []) {
  const saved = []
  const call = async (path, { body } = {}) => {
    if (path === '/smart-search') return { results: existing.map((m, i) => ({ obsId: `mem_${i}`, score: 0.9 })) }
    if (path.startsWith('/memories/')) {
      const i = Number(path.split('_')[1])
      return { memory: { id: `mem_${i}`, agentId: 'ws-loja', content: existing[i] } }
    }
    if (path === '/remember') {
      saved.push(body)
      return { memory: { id: `mem_new${saved.length}` } }
    }
    throw new Error(`rota inesperada ${path}`)
  }
  return { call, saved }
}

test('lê o array JSON mesmo com texto em volta e descarta item fraco', () => {
  const items = parseItems('Segue:\n[{"type":"bug","content":"O desconto do ItemVenda é recalculado em VendaService.recalcular()","files":["seller/VendaService.cs"]},{"content":"curto"}]\nfim')
  assert.equal(items.length, 1)
  assert.equal(items[0].type, 'bug')
  assert.deepEqual(items[0].files, ['seller/VendaService.cs'])
  assert.deepEqual(parseItems('nada a gravar'), [])
  assert.deepEqual(parseItems('[{"type":"x","content":'), [])
})

test('grava o que o extrator devolveu, com o que já existe no prompt', async () => {
  const mem = fakeMemory(['A NFS-e de SP é montada em NFSEXMLENV.prw'])
  let prompt = ''
  const ask = async (p, model) => {
    prompt = p
    assert.equal(model, 'claude-sonnet-5')
    return '[{"type":"fact","content":"O lote de RPS é transmitido ao TSS pela função TSSEnvLote em TSSNFSE.prw","files":["PROTEUS/TSSNFSE.prw"],"concepts":["rps","tss"]}]'
  }

  const result = await extractAndSave(mem.call, {
    workspace: 'loja', question: 'onde o RPS vai para o TSS?', answer: 'Em TSSNFSE.prw, função TSSEnvLote…', model: 'claude-sonnet-5',
  }, ask)

  assert.equal(result.saved, 1)
  assert.match(prompt, /## Já gravado\n- A NFS-e de SP é montada em NFSEXMLENV\.prw/)
  assert.equal(mem.saved[0].agentId, 'ws-loja')
  assert.deepEqual(mem.saved[0].files, ['PROTEUS/TSSNFSE.prw'])
})

test('resposta vazia ou extrator sem itens não grava nada', async () => {
  const mem = fakeMemory()
  assert.deepEqual(await extractAndSave(mem.call, { workspace: 'loja', question: 'oi', answer: '' }, async () => '[]'), { saved: 0, memories: [] })
  assert.deepEqual(await extractAndSave(mem.call, { workspace: 'loja', question: 'oi', answer: 'olá' }, async () => '[]'), { saved: 0, memories: [] })
  assert.equal(mem.saved.length, 0)
})

test('prompt corta pergunta e resposta enormes', () => {
  const prompt = buildPrompt({ question: 'q'.repeat(10000), answer: 'a'.repeat(50000), existing: [] })
  assert.ok(prompt.length < 20000)
  assert.match(prompt, /nada gravado sobre isso/)
})
