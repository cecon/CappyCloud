'use strict'
// ──────────────────────────────────────────────────────────────
// Handlers HTTP de git invocados pela API CappyCloud.
//   POST /git/ls-remote-branches  → git ls-remote --heads <url>
//   POST /git/origin-head-branch  → symbolic-ref local (sem rede)
//   POST /git/branch-r            → git branch -r no clone /repos/...
//   GET  /git/ls-files            → git ls-files num worktree
//   GET  /git/file                → conteúdo de ficheiro num worktree
// Exporta `tryHandle(req, res, helpers)` que devolve `true` se tratou.
// ──────────────────────────────────────────────────────────────

const { execFile } = require('child_process')
const fs = require('fs')
const path = require('path')
const { promisify } = require('util')

const execFileAsync = promisify(execFile)

async function lsRemoteBranches(body, json, res, injectToken) {
  let { url: remoteUrl } = body
  if (!remoteUrl || typeof remoteUrl !== 'string') {
    return json(res, 400, { error: 'url is required' })
  }
  remoteUrl = injectToken(remoteUrl)
  try {
    const { stdout, stderr } = await execFileAsync(
      'git',
      ['ls-remote', '--heads', remoteUrl],
      {
        env: { ...process.env, GIT_TERMINAL_PROMPT: '0' },
        timeout: 60_000,
        maxBuffer: 10 * 1024 * 1024,
      },
    )
    return json(res, 200, { stdout: stdout || '', stderr: stderr || '' })
  } catch (err) {
    return json(res, 200, {
      stdout: err.stdout != null ? String(err.stdout) : '',
      stderr: err.stderr != null ? String(err.stderr) : String(err.message || ''),
    })
  }
}

async function originHeadBranch(body, json, res) {
  const { repo_path: repoPath } = body
  if (!repoPath || typeof repoPath !== 'string' || !repoPath.startsWith('/repos/')) {
    return json(res, 400, { error: 'repo_path must be under /repos/' })
  }
  try {
    const { stdout } = await execFileAsync(
      'git',
      ['-C', repoPath, 'symbolic-ref', '--short', 'refs/remotes/origin/HEAD'],
      { timeout: 10_000 },
    )
    const line = (stdout || '').trim()
    let branch = ''
    if (line.startsWith('origin/')) branch = line.slice('origin/'.length)
    return json(res, 200, { branch })
  } catch {
    return json(res, 200, { branch: '' })
  }
}

async function branchR(body, json, res) {
  const { repo_path: repoPath } = body
  if (!repoPath || typeof repoPath !== 'string' || !repoPath.startsWith('/repos/')) {
    return json(res, 400, { error: 'repo_path must be under /repos/' })
  }
  try {
    const { stdout, stderr } = await execFileAsync(
      'git',
      ['-C', repoPath, 'branch', '-r'],
      { timeout: 30_000, maxBuffer: 1024 * 1024 },
    )
    return json(res, 200, { stdout: stdout || '', stderr: stderr || '' })
  } catch (err) {
    return json(res, 200, {
      stdout: err.stdout != null ? String(err.stdout) : '',
      stderr: err.stderr != null ? String(err.stderr) : String(err.message || ''),
    })
  }
}

/**
 * Tenta tratar um endpoint /git/*. Retorna true se tratou, false caso contrário.
 * @param {http.IncomingMessage} req
 * @param {http.ServerResponse} res
 * @param {{json: Function, readBody: Function, injectToken: Function}} helpers
 */
async function tryHandle(req, res, { json, readBody, injectToken }) {
  const urlPath = (req.url || '').split('?')[0]
  const url = new URL(req.url || '/', 'http://localhost')

  if (req.method === 'GET' && urlPath === '/git/ls-files') {
    const worktree_path = url.searchParams.get('worktree_path') || ''
    if (!worktree_path) { json(res, 400, { error: 'worktree_path is required' }); return true }
    try {
      const { stdout } = await execFileAsync('git', ['-C', worktree_path, 'ls-files'],
        { timeout: 15_000, maxBuffer: 4 * 1024 * 1024 })
      json(res, 200, { worktree_path, files: stdout.split('\n').filter(Boolean) })
    } catch (err) {
      json(res, 500, { error: ((err.stdout || '') + (err.stderr || '')).trim() || err.message })
    }
    return true
  }

  if (req.method === 'GET' && urlPath === '/git/file') {
    const worktree_path = url.searchParams.get('worktree_path') || ''
    const filePath = url.searchParams.get('path') || ''
    if (!worktree_path) { json(res, 400, { error: 'worktree_path is required' }); return true }
    if (!filePath) { json(res, 400, { error: 'path is required' }); return true }
    const resolved = path.resolve(worktree_path, filePath)
    if (!resolved.startsWith(path.resolve(worktree_path))) { json(res, 400, { error: 'Caminho inválido' }); return true }
    try {
      json(res, 200, { path: filePath, content: fs.readFileSync(resolved, 'utf8') })
    } catch (err) {
      if (err.code === 'ENOENT') json(res, 404, { error: 'Ficheiro não encontrado' })
      else json(res, 500, { error: err.message })
    }
    return true
  }

  if (req.method !== 'POST') return false

  if (urlPath === '/git/ls-remote-branches') {
    return lsRemoteBranches(await readBody(req), json, res, injectToken) && true
  }
  if (urlPath === '/git/origin-head-branch') {
    return originHeadBranch(await readBody(req), json, res) && true
  }
  if (urlPath === '/git/branch-r') {
    return branchR(await readBody(req), json, res) && true
  }
  return false
}

module.exports = { tryHandle }
