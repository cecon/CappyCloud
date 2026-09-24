'use strict'
// node --test services/sandbox/tests/session_paths.test.js
const test = require('node:test')
const assert = require('node:assert/strict')

const { assertInsideSession, sessionRootInfo, workspaceRepoPath } = require('../session_paths')

test('aceita raízes de sessão legadas e de workspace', () => {
  assert.deepEqual(sessionRootInfo('/repos/sessions/abc123'), { root: '/repos/sessions/abc123', workspaceRoot: null })
  assert.deepEqual(sessionRootInfo('/repos/workspaces/loja/sessions/abc123'), {
    root: '/repos/workspaces/loja/sessions/abc123',
    workspaceRoot: '/repos/workspaces/loja',
  })
})

test('recusa raízes fora das áreas de sessão ou com escape', () => {
  for (const bad of [
    '/repos/sessions',
    '/repos/seller',
    '/repos/workspaces/loja',
    '/repos/workspaces/loja/sessions',
    '/repos/workspaces/Loja/sessions/abc',
    '/repos/workspaces/loja/sessions/abc/../../../seller',
    '/etc',
  ]) {
    assert.throws(() => sessionRootInfo(bad), /session_root must be/, bad)
  }
})

test('worktrees e arquivos precisam estar dentro de uma sessão', () => {
  assert.equal(assertInsideSession('/repos/sessions/abc/seller'), '/repos/sessions/abc/seller')
  assert.equal(
    assertInsideSession('/repos/workspaces/loja/sessions/abc/backend/src/app.py'),
    '/repos/workspaces/loja/sessions/abc/backend/src/app.py',
  )
  assert.throws(() => assertInsideSession('/repos/workspaces/loja/knowledge/x'), /inside a session/)
  assert.throws(() => assertInsideSession('/repos/sessions/abc'), /inside a session/)
  assert.throws(() => assertInsideSession('/repos/seller/.git'), /inside a session/)
})

test('repos somente leitura do workspace: só o clone, sem escape nem subpasta', () => {
  assert.equal(workspaceRepoPath('/repos/workspaces/loja/repos/backend'), '/repos/workspaces/loja/repos/backend')
  for (const bad of [
    '/repos/workspaces/loja/repos',
    '/repos/workspaces/loja/repos/backend/src',
    '/repos/workspaces/loja/repos/../sessions/abc',
    '/repos/backend',
  ]) {
    assert.throws(() => workspaceRepoPath(bad), /workspace repository/, bad)
  }
})
