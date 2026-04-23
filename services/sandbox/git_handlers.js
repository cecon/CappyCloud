'use strict'
// ──────────────────────────────────────────────────────────────
// Handlers HTTP de git invocados pela API CappyCloud.
//   POST /git/ls-remote-branches  → git ls-remote --heads <url>
//   POST /git/origin-head-branch  → symbolic-ref local (sem rede)
//   POST /git/branch-r            → git branch -r no clone /repos/...
// Exporta `tryHandle(req, res, helpers)` que devolve `true` se tratou.
// ──────────────────────────────────────────────────────────────

const { execFile } = require('child_process')
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
  if (req.method !== 'POST' || !req.url) return false
  const path = req.url.split('?')[0]

  if (path === '/git/ls-remote-branches') {
    return lsRemoteBranches(await readBody(req), json, res, injectToken) && true
  }
  if (path === '/git/origin-head-branch') {
    return originHeadBranch(await readBody(req), json, res) && true
  }
  if (path === '/git/branch-r') {
    return branchR(await readBody(req), json, res) && true
  }
  return false
}

module.exports = { tryHandle }
