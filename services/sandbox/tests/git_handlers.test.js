'use strict'
// node --test services/sandbox/tests/git_handlers.test.js
const test = require('node:test')
const assert = require('node:assert/strict')

const { tryHandle } = require('../git_handlers')

async function call(method, url, body = {}) {
  let result
  const helpers = {
    json: async (_res, status, payload) => { result = { status, payload } },
    readBody: async () => body,
    injectToken: (u) => u,
  }
  await tryHandle({ method, url }, {}, helpers)
  return result
}

test('ls-files e file recusam caminhos fora das sessões', async () => {
  for (const wt of ['/', '/etc', '/repos/seller', '/repos/sessions', '/repos/sessions/abc/../../..']) {
    const ls = await call('GET', `/git/ls-files?worktree_path=${encodeURIComponent(wt)}`)
    assert.equal(ls.status, 400, wt)
  }
  const file = await call('GET', `/git/file?worktree_path=%2F&path=etc%2Fpasswd`)
  assert.equal(file.status, 400)
  const escape = await call('GET', `/git/file?worktree_path=%2Frepos%2Fsessions%2Fabc%2Fseller&path=..%2F..%2Fx`)
  assert.equal(escape.status, 400)
})

test('rotas por repo_path normalizam o caminho antes de checar /repos/', async () => {
  for (const route of ['/git/origin-head-branch', '/git/branch-r']) {
    const out = await call('POST', route, { repo_path: '/repos/../etc' })
    assert.equal(out.status, 400, route)
  }
})
