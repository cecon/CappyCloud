'use strict'
// node --test services/sandbox/tests/terminal_handler.test.js
const test = require('node:test')
const assert = require('node:assert/strict')
const path = require('path')

process.env.INTERNAL_API_TOKEN = 'segredo-de-teste'
// Um "shell" falso que ecoa a entrada: o teste não depende de pty (Windows/CI).
process.env.TERMINAL_PTY_SCRIPT = path.join(__dirname, 'fixtures', 'fake_pty.py')
const handler = require('../terminal_handler')

function request(method, url, { token = 'segredo-de-teste', body = {} } = {}) {
  return new Promise((resolve) => {
    const res = {
      chunks: [],
      writeHead(status) { this.status = status },
      write(chunk) { this.chunks.push(chunk) },
      end(chunk) { if (chunk) this.chunks.push(chunk); this.ended = true },
      on() {},
    }
    const helpers = {
      json: async (_res, status, payload) => { resolve({ status, payload }) },
      readBody: async () => body,
    }
    handler.tryHandle({ method, url, headers: { 'x-internal-token': token } }, res, helpers)
      .then((handled) => { if (method === 'GET' && handled) resolve({ status: res.status, res }) })
  })
}

test('exige o token interno e rotas conhecidas', async () => {
  assert.equal((await request('POST', '/terminal/sessions', { token: 'errado' })).status, 401)
  assert.equal((await request('POST', '/terminal/outra')).status, 404)
  const missing = await request('POST', `/terminal/sessions/${'a'.repeat(32)}/input`, { body: { data: 'x' } })
  assert.equal(missing.status, 404)
})

test('abre, recebe entrada, devolve a saída e encerra', async (t) => {
  const python = require('child_process').spawnSync('python3', ['--version'])
  if (python.status !== 0) return t.skip('python3 indisponível')
  const created = await request('POST', '/terminal/sessions', { body: { cols: 80, rows: 24 } })
  assert.equal(created.status, 200)
  const id = created.payload.id
  assert.match(id, /^[a-f0-9]{32}$/)

  assert.equal((await request('POST', `/terminal/sessions/${id}/input`, { body: { data: 'oi\n' } })).status, 200)
  assert.equal((await request('POST', `/terminal/sessions/${id}/resize`, { body: { cols: 100, rows: 30 } })).status, 200)
  assert.equal((await request('POST', `/terminal/sessions/${id}/input`, { body: {} })).status, 400)

  await new Promise((r) => setTimeout(r, 400))
  const stream = await request('GET', `/terminal/sessions/${id}/stream`)
  assert.equal(stream.status, 200)
  const output = stream.res.chunks
    .map((line) => JSON.parse(line))
    .filter((event) => event.type === 'output')
    .map((event) => Buffer.from(event.data, 'base64').toString())
    .join('')
  assert.match(output, /eco: oi/)
  assert.match(output, /tamanho: 100x30/)

  assert.equal((await request('DELETE', `/terminal/sessions/${id}`)).status, 200)
  assert.equal(handler._sessions.has(id), false)
})

test('limita os terminais abertos', async (t) => {
  const python = require('child_process').spawnSync('python3', ['--version'])
  if (python.status !== 0) return t.skip('python3 indisponível')
  const ids = []
  for (let i = 0; i < 3; i++) ids.push((await request('POST', '/terminal/sessions')).payload.id)
  assert.equal((await request('POST', '/terminal/sessions')).status, 429)
  for (const id of ids) handler.closeSession(id)
})
