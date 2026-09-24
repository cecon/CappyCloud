'use strict'
// Usa symlinks POSIX (roda no container do sandbox ou em Linux):
//   node --test services/sandbox/tests/workspace_handler.test.js
const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('fs')
const os = require('os')
const path = require('path')

const { removeWorkspace, syncWorkspace } = require('../workspace_handler')

const posix = process.platform !== 'win32'

function reposRoot() {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'cappy-ws-'))
  for (const slug of ['seller', 'smartpos']) fs.mkdirSync(path.join(root, slug, '.git'), { recursive: true })
  return root
}

test('recusa slug e alias inválidos', () => {
  assert.throws(() => syncWorkspace({ slug: '../etc' }, { reposRoot: '/tmp/x' }), /slug inválido/)
  assert.throws(
    () => syncWorkspace({ slug: 'loja', repos: [{ alias: '../x', slug: 'seller' }] }, { reposRoot: '/tmp/x' }),
    /repo inválido/,
  )
})

test('cria a árvore, o CLAUDE.md e links para os clones do catálogo', { skip: !posix }, () => {
  const root = reposRoot()
  const result = syncWorkspace(
    { slug: 'loja', claude_md: '# Loja', repos: [{ alias: 'backend', slug: 'seller' }, { alias: 'pdv', slug: 'ausente' }] },
    { reposRoot: root },
  )
  const ws = path.join(root, 'workspaces', 'loja')

  for (const dir of ['.claude/skills', 'knowledge', 'memory', 'sessions']) assert.ok(fs.existsSync(path.join(ws, dir)))
  assert.equal(fs.readFileSync(path.join(ws, 'CLAUDE.md'), 'utf8'), '# Loja')
  assert.equal(fs.readlinkSync(path.join(ws, 'repos', 'backend')), path.join(root, 'seller'))
  assert.deepEqual(result.repos.map((r) => [r.alias, r.cloned]), [['backend', true], ['pdv', false]])
})

test('ressincronizar troca links, remove os que saíram e preserva pastas reais', { skip: !posix }, () => {
  const root = reposRoot()
  syncWorkspace({ slug: 'loja', repos: [{ alias: 'backend', slug: 'seller' }] }, { reposRoot: root })
  const reposDir = path.join(root, 'workspaces', 'loja', 'repos')
  fs.mkdirSync(path.join(reposDir, 'manual'))

  syncWorkspace({ slug: 'loja', claude_md: '', repos: [{ alias: 'pdv', slug: 'smartpos' }] }, { reposRoot: root })

  assert.ok(!fs.existsSync(path.join(reposDir, 'backend')))
  assert.equal(fs.readlinkSync(path.join(reposDir, 'pdv')), path.join(root, 'smartpos'))
  assert.ok(fs.existsSync(path.join(reposDir, 'manual')))
  assert.ok(!fs.existsSync(path.join(root, 'workspaces', 'loja', 'CLAUDE.md')))
  assert.ok(fs.existsSync(path.join(root, 'seller', '.git')), 'clone do catálogo intacto')
})

test('remoção recusa com sessões e nunca apaga o clone do catálogo', { skip: !posix }, () => {
  const root = reposRoot()
  syncWorkspace({ slug: 'loja', repos: [{ alias: 'backend', slug: 'seller' }] }, { reposRoot: root })
  const sessions = path.join(root, 'workspaces', 'loja', 'sessions')
  fs.mkdirSync(path.join(sessions, 'abc'))

  assert.equal(removeWorkspace('loja', { reposRoot: root }).busy, true)

  fs.rmdirSync(path.join(sessions, 'abc'))
  assert.equal(removeWorkspace('loja', { reposRoot: root }).removed, true)
  assert.ok(!fs.existsSync(path.join(root, 'workspaces', 'loja')))
  assert.ok(fs.existsSync(path.join(root, 'seller', '.git')))
})
