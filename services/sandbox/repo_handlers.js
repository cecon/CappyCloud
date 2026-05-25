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

function safeSlug(raw) {
  const slug = String(raw || '').trim()
  if (!/^[a-zA-Z0-9._-]+$/.test(slug)) throw new Error('slug inválido')
  return slug
}

function safeRepoPath(raw) {
  return path.join('/repos', safeSlug(raw))
}

function safeRepoFile(slug, relPath) {
  if (!relPath || typeof relPath !== 'string') throw new Error('path é obrigatório')
  if (relPath.includes('..') || path.isAbsolute(relPath)) throw new Error('path inválido')
  const repoPath = safeRepoPath(slug)
  const full = path.resolve(path.join(repoPath, relPath))
  const prefix = repoPath.endsWith('/') ? repoPath : repoPath + '/'
  if (full !== repoPath && !full.startsWith(prefix)) throw new Error('path fora do repo')
  return { repoPath, full }
}

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

async function listRepoFiles(slug, json, res) {
  try {
    const repoPath = safeRepoPath(slug)
    const { stdout } = await execFileAsync('git', ['-C', repoPath, 'ls-files'], {
      timeout: 30_000,
      maxBuffer: 10 * 1024 * 1024,
    })
    const files = String(stdout || '').split(/\r?\n/).map(l => l.trim()).filter(Boolean)
    return json(res, 200, { slug, repo_path: repoPath, files })
  } catch (err) {
    return json(res, 500, { error: 'git ls-files falhou', detail: err.message })
  }
}

async function readRepoFile(slug, url, json, res) {
  try {
    const relPath = url.searchParams.get('path') || ''
    const { full } = safeRepoFile(slug, relPath)
    return json(res, 200, { slug, path: relPath, content: fs.readFileSync(full, 'utf8') })
  } catch (err) {
    return json(res, err.code === 'ENOENT' ? 404 : 500, {
      error: err.code === 'ENOENT' ? 'Ficheiro não encontrado' : 'Erro ao ler ficheiro',
      detail: err.message,
    })
  }
}

async function searchRepo(slug, url, json, res) {
  try {
    const repoPath = safeRepoPath(slug)
    const query = (url.searchParams.get('q') || '').trim()
    const regex = url.searchParams.get('regex') === 'true'
    const limit = Math.max(1, Math.min(Number(url.searchParams.get('limit') || 20), 50))
    if (!query) return json(res, 400, { error: 'q é obrigatório' })
    const args = ['--line-number', '--ignore-case', '--max-count', '3']
    if (!regex) args.push('--fixed-strings')
    args.push('--', query, repoPath)
    const { stdout } = await execFileAsync('rg', args, {
      timeout: 45_000,
      maxBuffer: 4 * 1024 * 1024,
    }).catch((err) => {
      if (err.code === 1) return { stdout: '' }
      throw err
    })
    const matches = String(stdout || '').split(/\r?\n/).filter(Boolean).slice(0, limit).map((line) => {
      const parts = line.split(':')
      const file = parts.shift() || ''
      const lineNo = Number(parts.shift() || 0)
      return { path: path.relative(repoPath, file), line: lineNo, text: parts.join(':').trim().slice(0, 500) }
    })
    return json(res, 200, { slug, query, regex, matches })
  } catch (err) {
    return json(res, 500, { error: 'busca no repo falhou', detail: err.message })
  }
}

async function repoCommit(slug, url, json, res) {
  try {
    const repoPath = safeRepoPath(slug)
    const ref = (url.searchParams.get('ref') || 'HEAD').trim() || 'HEAD'
    const { stdout } = await execFileAsync('git', ['-C', repoPath, 'rev-parse', ref], {
      timeout: 15_000,
      maxBuffer: 1024 * 1024,
    })
    return json(res, 200, { slug, ref, commit_sha: String(stdout || '').trim() })
  } catch (err) {
    return json(res, 500, { error: 'rev-parse falhou', detail: err.message })
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
  const filesMatch = path.match(/^\/repos\/([^/]+)\/files$/)
  if (req.method === 'GET' && filesMatch) {
    await listRepoFiles(filesMatch[1], json, res)
    return true
  }
  const fileMatch = path.match(/^\/repos\/([^/]+)\/file$/)
  if (req.method === 'GET' && fileMatch) {
    await readRepoFile(fileMatch[1], url, json, res)
    return true
  }
  const searchMatch = path.match(/^\/repos\/([^/]+)\/search$/)
  if (req.method === 'GET' && searchMatch) {
    await searchRepo(searchMatch[1], url, json, res)
    return true
  }
  const commitMatch = path.match(/^\/repos\/([^/]+)\/commit$/)
  if (req.method === 'GET' && commitMatch) {
    await repoCommit(commitMatch[1], url, json, res)
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
