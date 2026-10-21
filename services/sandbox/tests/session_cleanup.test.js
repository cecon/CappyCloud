'use strict'
// Requer git e caminhos POSIX (roda no container do sandbox ou em Linux):
//   node --test services/sandbox/tests/session_cleanup.test.js
const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('fs')
const os = require('os')
const path = require('path')
const { execFileSync } = require('child_process')

const { assertSafeSessionRoot, cleanupSession } = require('../session_cleanup')

const posix = process.platform !== 'win32'

function git(cwd, ...args) {
  return execFileSync('git', ['-C', cwd, ...args], { encoding: 'utf8' }).trim()
}

/** /repos fake com um "remote", um clone principal e uma sessão com worktree. */
function scenario() {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'cappy-cleanup-'))
  const remote = path.join(root, 'remote.git')
  execFileSync('git', ['init', '--bare', '-b', 'main', remote])
  const main = path.join(root, 'seller')
  execFileSync('git', ['clone', remote, main], { stdio: 'ignore' })
  git(main, '-c', 'user.email=t@t', '-c', 'user.name=t', 'commit', '--allow-empty', '-m', 'init')
  git(main, 'push', 'origin', 'main')
  const sessionRoot = path.join(root, 'sessions', 'abc123')
  const worktree = path.join(sessionRoot, 'seller')
  fs.mkdirSync(sessionRoot, { recursive: true })
  git(main, 'worktree', 'add', '-b', 'cappy/seller/abc123-seller', worktree, 'origin/main')
  const repos = JSON.stringify([
    { slug: 'seller', alias: 'seller', branch_name: 'cappy/seller/abc123-seller', worktree_path: worktree },
  ])
  return { root, main, sessionRoot, worktree, repos }
}

test('recusa raízes fora das áreas de sessão', () => {
  assert.throws(() => assertSafeSessionRoot('/etc'), /session_root must be/)
  assert.throws(() => assertSafeSessionRoot('/repos/sessions'), /session_root must be/)
  assert.throws(() => assertSafeSessionRoot('/repos/sessions/../seller'), /session_root must be/)
  assert.equal(assertSafeSessionRoot('/repos/sessions/abc'), '/repos/sessions/abc')
})

test('mantém sessão com alteração não commitada', { skip: !posix }, async () => {
  const s = scenario()
  fs.writeFileSync(path.join(s.worktree, 'novo.txt'), 'wip')

  const result = await cleanupSession({ session_root: s.sessionRoot, repos: s.repos }, undefined, { reposRoot: s.root })

  assert.equal(result.deleted, false)
  assert.match(result.blocked[0].reason, /não commitadas/)
  assert.ok(fs.existsSync(s.worktree))
})

test('mantém sessão com commit sem push, mesmo sem repos informados', { skip: !posix }, async () => {
  const s = scenario()
  fs.writeFileSync(path.join(s.worktree, 'novo.txt'), 'feito')
  git(s.worktree, 'add', '.')
  git(s.worktree, '-c', 'user.email=t@t', '-c', 'user.name=t', 'commit', '-m', 'wip')

  const result = await cleanupSession({ session_root: s.sessionRoot, repos: '[]' }, undefined, { reposRoot: s.root })

  assert.equal(result.deleted, false)
  assert.match(result.blocked[0].reason, /1 commit\(s\) sem push/)
})

test('apaga sessão limpa, remove a branch local e poda o clone', { skip: !posix }, async () => {
  const s = scenario()

  const result = await cleanupSession(
    { session_root: s.sessionRoot, repos: JSON.stringify(s.repos) },
    undefined,
    { reposRoot: s.root },
  )

  assert.equal(result.deleted, true)
  assert.ok(!fs.existsSync(s.sessionRoot))
  assert.equal(git(s.main, 'branch', '--list', 'cappy/seller/abc123-seller'), '')
  assert.ok(!git(s.main, 'worktree', 'list').includes('abc123'))
})

test('force apaga mesmo com trabalho pendente', { skip: !posix }, async () => {
  const s = scenario()
  fs.writeFileSync(path.join(s.worktree, 'novo.txt'), 'wip')

  const result = await cleanupSession(
    { session_root: s.sessionRoot, repos: s.repos, force: true },
    undefined,
    { reposRoot: s.root },
  )

  assert.equal(result.deleted, true)
  assert.ok(!fs.existsSync(s.sessionRoot))
})

test('CLAUDE.md injetado pelo CappyCloud não conta como trabalho pendente', { skip: !posix }, async () => {
  const s = scenario()
  fs.writeFileSync(path.join(s.worktree, 'CLAUDE.md'), '# template do CappyCloud')

  const result = await cleanupSession({ session_root: s.sessionRoot, repos: s.repos }, undefined, { reposRoot: s.root })

  assert.equal(result.deleted, true)
})

test('commits da base local (sem remote) não bloqueiam; só os da sessão', { skip: !posix }, async () => {
  const s = scenario()
  // Base local com commit que nunca foi para o remote.
  git(s.main, 'checkout', '-q', '-b', 'base-local')
  git(s.main, '-c', 'user.email=t@t', '-c', 'user.name=t', 'commit', '--allow-empty', '-m', 'local')
  const wt = path.join(s.sessionRoot, 'outra')
  git(s.main, 'worktree', 'add', '-b', 'cappy/seller/abc123-outra', wt, 'base-local')
  const repos = JSON.stringify([{ slug: 'seller', alias: 'outra', branch_name: 'cappy/seller/abc123-outra' }])

  const clean = await cleanupSession({ session_root: s.sessionRoot, repos }, undefined, { reposRoot: s.root })
  assert.equal(clean.deleted, true)
})
