'use strict'
// Onde sessões (worktrees de conversa) podem existir no sandbox:
//   <repos>/sessions/<id>/                        — conversas por repositório (legado)
//   <repos>/workspaces/<slug>/sessions/<id>/      — conversas de workspace
// Tudo que cria, lê ou apaga worktrees de sessão valida o caminho por aqui.

const path = require('path').posix

const WORKSPACE_SLUG = '[a-z0-9][a-z0-9-]{1,62}'
const SESSION_ID = '[A-Za-z0-9][A-Za-z0-9._-]*'

function escapeRoot(reposRoot) {
  return reposRoot.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

function patterns(reposRoot) {
  const root = escapeRoot(reposRoot)
  return [
    new RegExp(`^${root}/sessions/${SESSION_ID}$`),
    new RegExp(`^${root}/workspaces/(${WORKSPACE_SLUG})/sessions/${SESSION_ID}$`),
  ]
}

/**
 * Valida uma raiz de sessão e devolve `{ root, workspaceRoot }`
 * (`workspaceRoot` é null para sessões legadas). Lança erro fora das áreas permitidas.
 */
function sessionRootInfo(candidate, reposRoot = '/repos') {
  const root = path.resolve(String(candidate || ''))
  const [legacy, workspace] = patterns(reposRoot)
  if (legacy.test(root)) return { root, workspaceRoot: null }
  const match = root.match(workspace)
  if (match) return { root, workspaceRoot: path.join(reposRoot, 'workspaces', match[1]) }
  throw new Error(`session_root must be ${reposRoot}/sessions/<id> or ${reposRoot}/workspaces/<ws>/sessions/<id>`)
}

/**
 * Clone de um repositório somente leitura do workspace
 * (`<repos>/workspaces/<ws>/repos/<alias>`): só leitura, nunca diff/push.
 */
function workspaceRepoPath(candidate, reposRoot = '/repos') {
  const resolved = path.resolve(String(candidate || ''))
  const re = new RegExp(`^${escapeRoot(reposRoot)}/workspaces/${WORKSPACE_SLUG}/repos/[A-Za-z0-9][A-Za-z0-9._-]{0,127}$`)
  if (!re.test(resolved)) throw new Error('path must be a workspace repository')
  return resolved
}

/** Caminho (worktree ou arquivo) dentro de alguma raiz de sessão, nunca a raiz em si. */
function assertInsideSession(candidate, reposRoot = '/repos') {
  const resolved = path.resolve(String(candidate || ''))
  let current = resolved
  while (current !== path.dirname(current)) {
    const parent = path.dirname(current)
    try {
      sessionRootInfo(parent, reposRoot)
      return resolved
    } catch {
      current = parent
    }
  }
  throw new Error('path must be inside a session root')
}

module.exports = { assertInsideSession, sessionRootInfo, workspaceRepoPath }
