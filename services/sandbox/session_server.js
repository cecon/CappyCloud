#!/usr/bin/env node
'use strict'
// ──────────────────────────────────────────────────────────────
// Session Server — HTTP sidecar para gerenciar sessões multi-repo
//
// Substitui o docker exec que o EnvironmentManager usava.
// Cada sessão tem um session_root que contém um worktree por repo:
//
//   /repos/sessions/<session_id>/
//     <alias-1>/   ← git worktree de /repos/<slug-1> (branch: branch_name)
//     <alias-2>/   ← git worktree de /repos/<slug-2> (branch: branch_name)
//
// Endpoints:
//   POST   /sessions               → cria session_root + worktrees
//   DELETE /sessions/:id           → remove session_root e faz worktree prune
//   GET    /health                 → liveness probe
// ──────────────────────────────────────────────────────────────

const http = require('http')
const fs = require('fs')
const path = require('path')
const { execFile, execFileSync } = require('child_process')
const { promisify } = require('util')

const execFileAsync = promisify(execFile)
const PORT = parseInt(process.env.SESSION_SERVER_PORT || '8080', 10)

/**
 * Injeta tokens de autenticação na URL git antes de clonar/fazer fetch.
 * Suporta Azure DevOps (DEVOPS_TOKEN) e GitHub (GITHUB_TOKEN).
 * @param {string} url
 * @returns {string}
 */
function injectToken(url) {
  const devopsToken = process.env.DEVOPS_TOKEN || ''
  const githubToken = process.env.GITHUB_TOKEN || ''
  let result = url
  if (devopsToken && result.includes('dev.azure.com')) {
    result = result.replace(/https:\/\/([^@]*@)?dev\.azure\.com/, `https://pat:${devopsToken}@dev.azure.com`)
  }
  if (githubToken && result.includes('github.com')) {
    result = result.replace(/https:\/\/([^@]*@)?github\.com/, `https://x-token:${githubToken}@github.com`)
  }
  return result
}

function json(res, status, body) {
  const payload = JSON.stringify(body)
  res.writeHead(status, {
    'Content-Type': 'application/json',
    'Content-Length': Buffer.byteLength(payload),
  })
  res.end(payload)
}

function readBody(req) {
  return new Promise((resolve, reject) => {
    let data = ''
    req.on('data', chunk => { data += chunk })
    req.on('end', () => {
      try { resolve(data ? JSON.parse(data) : {}) }
      catch { reject(new Error('Invalid JSON body')) }
    })
    req.on('error', reject)
  })
}

// ── Cria um worktree via session_start.sh ──────────────────────
async function createWorktree({ slug, alias, base_branch, branch_name, worktree_path, clone_url = '' }) {
  const args = [slug, alias, worktree_path, base_branch || '', branch_name || '', clone_url]
  const { stdout, stderr } = await execFileAsync('/session_start.sh', args, {
    env: { ...process.env },
    timeout: 60_000,
  })
  return (stdout + stderr).trim()
}

// ── Remove session_root e prune worktrees ─────────────────────
async function destroySession({ session_root, repos }) {
  if (session_root) {
    await execFileAsync('rm', ['-rf', session_root], { timeout: 30_000 }).catch(() => {})
  }

  const slugs = new Set((repos || []).map(r => r.slug).filter(Boolean))
  for (const slug of slugs) {
    await execFileAsync(
      'git', ['-C', `/repos/${slug}`, 'worktree', 'prune'],
      { timeout: 30_000 }
    ).catch(() => {})
  }
}

// ── HTTP server ───────────────────────────────────────────────
const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, `http://localhost:${PORT}`)
  const pathname = url.pathname

  try {
    // GET /health
    if (req.method === 'GET' && pathname === '/health') {
      return json(res, 200, { status: 'ok' })
    }

    // POST /sessions — cria sessão multi-repo
    if (req.method === 'POST' && pathname === '/sessions') {
      const body = await readBody(req)
      const {
        session_id,
        repos = [],
        session_root = '',
      } = body

      if (!session_id) {
        return json(res, 400, { error: 'session_id is required' })
      }

      if (!session_root) {
        return json(res, 400, { error: 'session_root is required' })
      }

      const outputs = []

      fs.mkdirSync(session_root, { recursive: true })

      // Injeta CLAUDE.md na raiz da sessão
      if (fs.existsSync('/app/CLAUDE.md')) {
        fs.copyFileSync('/app/CLAUDE.md', path.join(session_root, 'CLAUDE.md'))
      }

      for (const repo of repos) {
        const { slug, alias, base_branch: rb, branch_name, clone_url: rc } = repo
        if (!slug || !alias) continue
        const wt_path = path.join(session_root, alias)
        try {
          const out = await createWorktree({
            slug,
            alias,
            base_branch: rb || 'main',
            branch_name: branch_name || `cappy/${slug}/${session_id}-${alias}`,
            worktree_path: wt_path,
            clone_url: rc || '',
          })
          outputs.push(`[${alias}] ${out}`)
          console.log(`[session_server] created worktree ${wt_path}`)
        } catch (err) {
          const msg = ((err.stdout || '') + (err.stderr || '')).trim() || err.message
          console.error(`[session_server] failed worktree ${wt_path}: ${msg}`)
          outputs.push(`[${alias}] ERROR: ${msg}`)
        }
      }

      return json(res, 200, {
        session_id,
        session_root,
        output: outputs.join('\n'),
      })
    }

    // DELETE /sessions/:id — remove sessão
    const deleteMatch = pathname.match(/^\/sessions\/([^/]+)$/)
    if (req.method === 'DELETE' && deleteMatch) {
      const session_id = deleteMatch[1]
      const session_root = url.searchParams.get('session_root') || ''
      let repos = []
      try { repos = JSON.parse(url.searchParams.get('repos') || '[]') } catch {}

      await destroySession({ session_root, repos })
      console.log(`[session_server] removed session ${session_id}`)
      return json(res, 200, { deleted: true, session_id })
    }

    // POST /repos/clone — clona ou atualiza um repo no volume
    if (req.method === 'POST' && pathname === '/repos/clone') {
      const { slug, clone_url, default_branch = 'main' } = await readBody(req)
      if (!slug || !clone_url) {
        return json(res, 400, { error: 'slug e clone_url são obrigatórios' })
      }
      const repoPath = `/repos/${slug}`
      try {
        if (fs.existsSync(path.join(repoPath, '.git'))) {
          await execFileAsync('git', ['-C', repoPath, 'fetch', '--all'], {
            env: { ...process.env, GIT_TERMINAL_PROMPT: '0' }, timeout: 120_000,
          })
          console.log(`[session_server] fetched ${slug}`)
        } else {
          fs.mkdirSync(repoPath, { recursive: true })
          const authCloneUrl = injectToken(clone_url)
          await execFileAsync('git', ['clone', '--branch', default_branch, authCloneUrl, repoPath], {
            env: { ...process.env, GIT_TERMINAL_PROMPT: '0' },
            timeout: 300_000,
          })
          console.log(`[session_server] cloned ${slug}`)
        }
        return json(res, 200, { cloned: true, slug, path: repoPath })
      } catch (err) {
        const msg = ((err.stdout || '') + (err.stderr || '')).trim() || err.message
        console.error(`[session_server] clone failed ${slug}: ${msg}`)
        return json(res, 500, { error: msg })
      }
    }

    // DELETE /repos/:slug — remove repo do volume
    const repoMatch = pathname.match(/^\/repos\/([^/]+)$/)
    if (req.method === 'DELETE' && repoMatch) {
      const slug = repoMatch[1]
      const repoPath = `/repos/${slug}`
      try {
        await execFileAsync('rm', ['-rf', repoPath], { timeout: 60_000 })
        console.log(`[session_server] removed repo ${slug}`)
        return json(res, 200, { removed: true, slug })
      } catch (err) {
        return json(res, 500, { error: err.message })
      }
    }

    // POST /git-auth — reconfigura credenciais git (token atualizado no DB)
    if (req.method === 'POST' && pathname === '/git-auth') {
      const { provider_type, token, base_url } = await readBody(req)
      try {
        if (provider_type === 'github' && token) {
          await execFileAsync('gh', ['auth', 'login', '--with-token'], {
            input: token,
            timeout: 30_000,
          }).catch(() => {
            // gh auth login via stdin pode não estar disponível — usar git credential
            execFileSync('git', ['config', '--global', `url.https://x-token:${token}@github.com/.insteadOf`, 'https://github.com/'])
          })
        } else if (provider_type === 'azure_devops' && token) {
          process.env.AZURE_DEVOPS_EXT_PAT = token
          if (base_url) {
            execFileSync('git', ['config', '--global', `url.https://:${token}@${new URL(base_url).host}/.insteadOf`, base_url])
          }
        }
        console.log(`[session_server] git-auth updated for ${provider_type}`)
        return json(res, 200, { updated: true })
      } catch (err) {
        return json(res, 500, { error: err.message })
      }
    }

    return json(res, 404, { error: 'Not found' })
  } catch (err) {
    console.error('[session_server] Unhandled error:', err)
    return json(res, 500, { error: 'Internal server error' })
  }
})

server.listen(PORT, '0.0.0.0', () => {
  console.log(`[session_server] listening on :${PORT}`)
})
