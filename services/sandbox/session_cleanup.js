'use strict'
// Remoção segura de sessões: valida o caminho, recusa apagar worktrees com
// trabalho não enviado (alterações não commitadas ou commits sem push) e,
// depois de apagar, remove a branch local da sessão e poda o clone principal.
// `run(cmd, args, opts)` é injetável para testes (padrão: execFile promisificado).

const path = require('path').posix
const fs = require('fs')
const { execFile } = require('child_process')
const { promisify } = require('util')
const { sessionRootInfo } = require('./session_paths')

const REPOS_ROOT = '/repos'
const SAFE_SLUG = /^[A-Za-z0-9][A-Za-z0-9._-]*$/
const defaultRun = promisify(execFile)

/** Só aceita raízes de sessão válidas (legadas ou de workspace); ver session_paths.js. */
function assertSafeSessionRoot(candidate, reposRoot = REPOS_ROOT) {
  return sessionRootInfo(candidate, reposRoot).root
}

function parseRepos(repos) {
  let list = repos
  // Aceita JSON duplamente codificado (registro antigo com repos em texto).
  for (let depth = 0; typeof list === 'string' && depth < 2; depth += 1) {
    try { list = JSON.parse(list) } catch { list = [] }
  }
  return Array.isArray(list) ? list.filter((repo) => repo && typeof repo === 'object') : []
}

/** Worktrees da sessão, com slug validado e caminho preso ao session_root. */
function sessionWorktrees(sessionRoot, repos) {
  const worktrees = []
  for (const repo of parseRepos(repos)) {
    const slug = String(repo.slug || '')
    const alias = String(repo.alias || slug)
    if (!SAFE_SLUG.test(slug) || !SAFE_SLUG.test(alias)) continue
    const worktreePath = path.resolve(repo.worktree_path || path.join(sessionRoot, alias))
    const relative = path.relative(sessionRoot, worktreePath)
    if (!relative || relative.startsWith('..') || path.isAbsolute(relative)) continue
    worktrees.push({ slug, alias, worktreePath, branch: String(repo.branch_name || '') })
  }
  return worktrees
}

async function gitOutput(run, args) {
  const { stdout } = await run('git', args, { timeout: 30_000 })
  return String(stdout || '').trim()
}

/** Toda subpasta com .git dentro da sessão, mesmo as que não vieram em `repos`. */
function discoveredWorktrees(sessionRoot) {
  try {
    return fs.readdirSync(sessionRoot, { withFileTypes: true })
      .filter((entry) => entry.isDirectory())
      .map((entry) => path.join(sessionRoot, entry.name))
      .filter((dir) => fs.existsSync(path.join(dir, '.git')))
  } catch {
    return []
  }
}

// Arquivos que o próprio CappyCloud injeta no worktree (session_start.sh); sessões
// antigas não os têm no info/exclude, então apareceriam como "não rastreados".
const INJECTED_UNTRACKED = new Set(['?? CLAUDE.md', '?? .claude/'])

/** Motivo para NÃO apagar o worktree, ou null se não há trabalho a perder. */
async function pendingWork(run, worktreePath) {
  if (!fs.existsSync(path.join(worktreePath, '.git'))) return null
  try {
    const status = (await gitOutput(run, ['-C', worktreePath, 'status', '--porcelain']))
      .split('\n')
      .filter((line) => line && !INJECTED_UNTRACKED.has(line))
    if (status.length) return 'alterações não commitadas'
    // Commits que só existem na branch desta sessão: fora de qualquer remote e
    // de qualquer outra branch local (a base pode ser uma branch local sem remote).
    const ownBranch = await gitOutput(run, ['-C', worktreePath, 'symbolic-ref', '--short', '-q', 'HEAD']).catch(() => '')
    // Com --branches, o --exclude usa o nome curto (sem refs/heads/).
    const exclude = ownBranch ? [`--exclude=${ownBranch}`] : []
    const unpushed = Number(
      await gitOutput(run, [
        '-C', worktreePath, 'rev-list', '--count', 'HEAD', '--not', ...exclude, '--branches', '--remotes',
      ]),
    )
    if (unpushed > 0) return `${unpushed} commit(s) sem push`
    return null
  } catch (err) {
    // Na dúvida, não apaga: melhor ocupar disco do que perder trabalho.
    return `não foi possível verificar (${err.message})`
  }
}

/**
 * Remove a sessão. Com `force=false` (padrão), devolve `{ deleted: false, blocked }`
 * se algum worktree tiver trabalho não enviado, sem apagar nada.
 */
async function cleanupSession(
  { session_root, repos, force = false },
  run = defaultRun,
  { reposRoot = REPOS_ROOT } = {},
) {
  const sessionRoot = assertSafeSessionRoot(session_root, reposRoot)
  const worktrees = sessionWorktrees(sessionRoot, repos)

  if (!force) {
    const blocked = []
    const toCheck = new Set([...worktrees.map((w) => w.worktreePath), ...discoveredWorktrees(sessionRoot)])
    for (const worktreePath of toCheck) {
      const reason = await pendingWork(run, worktreePath)
      if (reason) blocked.push({ alias: path.basename(worktreePath), worktree_path: worktreePath, reason })
    }
    if (blocked.length) return { deleted: false, blocked }
  }

  await run('rm', ['-rf', sessionRoot], { timeout: 60_000 }).catch(() => {})
  for (const slug of new Set(worktrees.map((worktree) => worktree.slug))) {
    const mainRepo = path.join(reposRoot, slug)
    await run('git', ['-C', mainRepo, 'worktree', 'prune'], { timeout: 30_000 }).catch(() => {})
    for (const worktree of worktrees.filter((item) => item.slug === slug && item.branch)) {
      // Trabalho enviado continua no remote; session_start.sh retoma de lá.
      await run('git', ['-C', mainRepo, 'branch', '-D', worktree.branch], { timeout: 30_000 }).catch(() => {})
    }
    await run('git', ['-C', mainRepo, 'gc', '--auto', '--quiet'], { timeout: 300_000 }).catch(() => {})
  }
  return { deleted: true, blocked: [] }
}

module.exports = { assertSafeSessionRoot, cleanupSession, sessionWorktrees }
