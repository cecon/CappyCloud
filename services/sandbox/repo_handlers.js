'use strict'
// ──────────────────────────────────────────────────────────────
// Handlers HTTP de gestão de clones de repositórios:
//   GET    /repos/list            → lista slugs clonados em /repos/<slug>/.git
//   POST   /repos/clone           → clona ou faz fetch (com PAT inline opcional)
//   DELETE /repos/:slug           → remove o clone do volume
// Exporta `tryHandle(req, res, helpers)`.
// ──────────────────────────────────────────────────────────────

const fs = require('fs')
const path = require('path')
const { execFile, execFileSync } = require('child_process')
const { promisify } = require('util')

const execFileAsync = promisify(execFile)

function configureInsteadOf(token, providerType, cloneUrl) {
  if (!token) return
  try {
    if (providerType === 'azure_devops' || /dev\.azure\.com/.test(cloneUrl)) {
      execFileSync('git', [
        'config', '--global',
        `url.https://pat:${token}@dev.azure.com/.insteadOf`,
        'https://dev.azure.com/',
      ])
    }
    if (providerType === 'github' || /github\.com/.test(cloneUrl)) {
      execFileSync('git', [
        'config', '--global',
        `url.https://x-token:${token}@github.com/.insteadOf`,
        'https://github.com/',
      ])
    }
  } catch (e) {
    console.warn(`[session_server] git config insteadOf failed: ${e.message}`)
  }
}

async function postClone(body, json, res, injectToken) {
  const { slug, clone_url, default_branch = 'main', token = '', provider_type = '' } = body
  if (!slug || !clone_url) {
    return json(res, 400, { error: 'slug e clone_url são obrigatórios' })
  }

  configureInsteadOf(token, provider_type, clone_url)

  const repoPath = `/repos/${slug}`
  const authCloneUrl = injectToken(clone_url, token, provider_type)
  const env = { ...process.env, GIT_TERMINAL_PROMPT: '0' }
  try {
    if (fs.existsSync(path.join(repoPath, '.git'))) {
      // Atualiza remote (clones antigos podem ter user@host sem PAT) e faz fetch.
      await execFileAsync(
        'git', ['-C', repoPath, 'remote', 'set-url', 'origin', authCloneUrl],
        { env, timeout: 10_000 },
      ).catch(() => {})
      await execFileAsync(
        'git', ['-C', repoPath, 'fetch', '--all', '--prune'],
        { env, timeout: 120_000 },
      )
      console.log(`[session_server] fetched ${slug}`)
    } else {
      fs.mkdirSync(repoPath, { recursive: true })
      try {
        await execFileAsync(
          'git', ['clone', '--branch', default_branch, authCloneUrl, repoPath],
          { env, timeout: 300_000 },
        )
      } catch {
        await execFileAsync(
          'git', ['clone', authCloneUrl, repoPath],
          { env, timeout: 300_000 },
        )
      }
      console.log(`[session_server] cloned ${slug}`)
    }
    return json(res, 200, { cloned: true, slug, path: repoPath })
  } catch (err) {
    const msg = ((err.stdout || '') + (err.stderr || '')).trim() || err.message
    console.error(`[session_server] clone failed ${slug}: ${msg}`)
    return json(res, 500, { error: msg })
  }
}

function listRepos(json, res) {
  try {
    const root = '/repos'
    if (!fs.existsSync(root)) return json(res, 200, { repos: [] })
    const entries = fs.readdirSync(root, { withFileTypes: true })
    const repos = entries
      .filter((e) => e.isDirectory() && e.name !== 'sessions')
      .map((e) => e.name)
      .filter((slug) => fs.existsSync(path.join(root, slug, '.git')))
      .sort()
    return json(res, 200, { repos })
  } catch (err) {
    return json(res, 500, { error: err.message })
  }
}

async function deleteRepo(slug, json, res) {
  try {
    await execFileAsync('rm', ['-rf', `/repos/${slug}`], { timeout: 60_000 })
    console.log(`[session_server] removed repo ${slug}`)
    return json(res, 200, { removed: true, slug })
  } catch (err) {
    return json(res, 500, { error: err.message })
  }
}

/**
 * Tenta tratar um endpoint /repos/*. Retorna true se tratou.
 */
async function tryHandle(req, res, { json, readBody, injectToken }) {
  if (!req.url) return false
  const url = new URL(req.url, 'http://localhost')
  const path = url.pathname

  if (req.method === 'GET' && path === '/repos/list') {
    await listRepos(json, res)
    return true
  }
  if (req.method === 'POST' && path === '/repos/clone') {
    const body = await readBody(req)
    await postClone(body, json, res, injectToken)
    return true
  }
  const m = path.match(/^\/repos\/([^/]+)$/)
  if (req.method === 'DELETE' && m) {
    await deleteRepo(m[1], json, res)
    return true
  }
  return false
}

module.exports = { tryHandle }
