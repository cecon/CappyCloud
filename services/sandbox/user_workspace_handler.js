'use strict'
// ──────────────────────────────────────────────────────────────
// Worktrees de usuário (/repos/users/...) e criação de worktree via
// session_start.sh, usados pelo session_server.js.
//
// Endpoints:
//   POST   /user-workspaces/ensure  → cria/reaproveita/repara o baseline
//   GET    /user-workspaces/status  → existe? está sujo?
//   DELETE /user-workspaces         → remove o diretório
// ──────────────────────────────────────────────────────────────

const fs = require('fs')
const path = require('path')
const { execFile } = require('child_process')
const { promisify } = require('util')

const execFileAsync = promisify(execFile)

// ── Cria um worktree via session_start.sh ──────────────────────
async function createWorktree({ slug, alias, base_branch, branch_name, worktree_path, clone_url = '' }) {
  const args = [slug, alias, worktree_path, base_branch || '', branch_name || '', clone_url]
  const { stdout, stderr } = await execFileAsync('/session_start.sh', args, {
    env: { ...process.env },
    timeout: 300_000,
  })
  const gitDir = path.join(worktree_path, '.git')
  if (!fs.existsSync(gitDir)) {
    throw new Error(`worktree não foi criado em ${worktree_path}`)
  }
  return (stdout + stderr).trim()
}

function assertSafeUserWorkspacePath(candidate) {
  const resolved = path.resolve(candidate || '')
  if (!resolved.startsWith('/repos/users/')) {
    throw new Error('workspace_path must be under /repos/users/')
  }
  return resolved
}

function worktreeExists(worktreePath) {
  return fs.existsSync(path.join(worktreePath, '.git'))
}

async function isGitClean(worktreePath) {
  const { stdout } = await execFileAsync('git', ['-C', worktreePath, 'status', '--porcelain'], {
    timeout: 30_000,
  })
  return stdout.trim() === ''
}

async function cleanUserWorkspace(worktreePath) {
  await execFileAsync('git', ['-C', worktreePath, 'reset', '--hard'], { timeout: 30_000 })
  await execFileAsync('git', ['-C', worktreePath, 'clean', '-fd'], { timeout: 30_000 })
}

async function sourceWorkspaceCommit(sourcePath) {
  const resolved = assertSafeUserWorkspacePath(sourcePath)
  if (!worktreeExists(resolved)) {
    throw new Error(`source_workspace_path missing: ${resolved}`)
  }
  if (!(await isGitClean(resolved))) {
    await cleanUserWorkspace(resolved)
  }
  const { stdout } = await execFileAsync('git', ['-C', resolved, 'rev-parse', 'HEAD'], {
    timeout: 30_000,
  })
  return stdout.trim()
}

async function ensureUserWorkspace({ slug, base_branch, workspace_path, clone_url = '' }) {
  if (!slug) throw new Error('slug is required')
  const workspacePath = assertSafeUserWorkspacePath(workspace_path)
  const branch = base_branch || 'main'
  const suffix = workspacePath.split('/').slice(-4).join('-')
  const branchName = `cappy/user-baselines/${slug}/${suffix}`
  let action = 'created'
  if (worktreeExists(workspacePath)) {
    action = 'reused'
    if (!(await isGitClean(workspacePath))) {
      await cleanUserWorkspace(workspacePath)
      action = 'repaired'
    }
  } else {
    if (fs.existsSync(workspacePath)) {
      await execFileAsync('rm', ['-rf', workspacePath], { timeout: 30_000 })
      action = 'repaired'
    }
    await createWorktree({
      slug,
      alias: slug,
      base_branch: branch,
      branch_name: branchName,
      worktree_path: workspacePath,
      clone_url,
    })
  }
  return {
    workspace_path: workspacePath,
    status: 'ready',
    action,
    dirty: false,
    message: action,
  }
}

async function handleEnsure(req, res, { json, readBody }) {
  const body = await readBody(req)
  try {
    const result = await ensureUserWorkspace(body)
    console.log(`[session_server] user workspace ${result.action}: ${result.workspace_path}`)
    json(res, 200, result)
  } catch (err) {
    console.error(`[session_server] user workspace ensure failed: ${err.message}`)
    json(res, 500, { error: err.message })
  }
}

async function handleStatus(res, { json, url }) {
  const workspace_path = url.searchParams.get('workspace_path') || ''
  try {
    const workspacePath = assertSafeUserWorkspacePath(workspace_path)
    const exists = worktreeExists(workspacePath)
    const dirty = exists ? !(await isGitClean(workspacePath)) : false
    json(res, 200, {
      workspace_path: workspacePath,
      exists,
      dirty,
      status: exists ? (dirty ? 'dirty' : 'ready') : 'missing',
    })
  } catch (err) {
    json(res, 400, { error: err.message })
  }
}

async function handleDelete(res, { json, url }) {
  const workspace_path = url.searchParams.get('workspace_path') || ''
  try {
    const workspacePath = assertSafeUserWorkspacePath(workspace_path)
    if (fs.existsSync(workspacePath)) {
      await execFileAsync('rm', ['-rf', workspacePath], { timeout: 30_000 })
    }
    json(res, 200, { deleted: true })
  } catch (err) {
    json(res, 400, { error: err.message })
  }
}

/**
 * Trata as rotas /user-workspaces*. `url` é o URL já parseado pelo servidor.
 * @returns {Promise<boolean>} true se a rota foi tratada
 */
async function tryHandle(req, res, { json, readBody, url }) {
  const pathname = url.pathname
  if (req.method === 'POST' && pathname === '/user-workspaces/ensure') {
    await handleEnsure(req, res, { json, readBody })
    return true
  }
  if (req.method === 'GET' && pathname === '/user-workspaces/status') {
    await handleStatus(res, { json, url })
    return true
  }
  if (req.method === 'DELETE' && pathname === '/user-workspaces') {
    await handleDelete(res, { json, url })
    return true
  }
  return false
}

module.exports = {
  assertSafeUserWorkspacePath,
  cleanUserWorkspace,
  createWorktree,
  ensureUserWorkspace,
  isGitClean,
  sourceWorkspaceCommit,
  tryHandle,
  worktreeExists,
}
