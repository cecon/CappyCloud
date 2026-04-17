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
async function createWorktree({ slug, alias, base_branch, branch_name, worktree_path }) {
  const args = [slug, alias, worktree_path, base_branch || '', branch_name || '']
  const { stdout, stderr } = await execFileAsync('/session_start.sh', args, {
    env: { ...process.env },
    timeout: 60_000,
  })
  return (stdout + stderr).trim()
}

// ── Remove session_root e prune worktrees ─────────────────────
async function destroySession({ session_root, repos, env_slug, worktree_path }) {
  // Remove o diretório raiz da sessão (contém todos os worktrees)
  const target = session_root || worktree_path
  if (target) {
    await execFileAsync('rm', ['-rf', target], { timeout: 30_000 }).catch(() => {})
  }

  // Prune worktree metadata em cada repo afetado
  const slugs = new Set((repos || []).map(r => r.slug).filter(Boolean))
  if (!session_root && env_slug) slugs.add(env_slug)

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

    // POST /sessions — cria sessão (multi-repo ou legacy single-repo)
    if (req.method === 'POST' && pathname === '/sessions') {
      const body = await readBody(req)
      const {
        session_id,
        repos = [],
        session_root = '',
        // Legacy single-repo
        env_slug = 'default',
        worktree_path = '',
        worktree_branch = '',
        base_branch = '',
      } = body

      if (!session_id) {
        return json(res, 400, { error: 'session_id is required' })
      }

      const outputs = []

      if (repos.length > 0 && session_root) {
        // ── Multi-repo: cria session_root + um worktree por repo ────
        fs.mkdirSync(session_root, { recursive: true })

        // Injeta CLAUDE.md na raiz da sessão
        if (fs.existsSync('/app/CLAUDE.md')) {
          fs.copyFileSync('/app/CLAUDE.md', path.join(session_root, 'CLAUDE.md'))
        }

        for (const repo of repos) {
          const { slug, alias, base_branch: rb, branch_name } = repo
          if (!slug || !alias) continue
          const wt_path = path.join(session_root, alias)
          try {
            const out = await createWorktree({
              slug,
              alias,
              base_branch: rb || base_branch || 'main',
              branch_name: branch_name || `cappy/${slug}/${session_id}-${alias}`,
              worktree_path: wt_path,
            })
            outputs.push(`[${alias}] ${out}`)
            console.log(`[session_server] created worktree ${wt_path}`)
          } catch (err) {
            const msg = ((err.stdout || '') + (err.stderr || '')).trim() || err.message
            console.error(`[session_server] failed worktree ${wt_path}: ${msg}`)
            outputs.push(`[${alias}] ERROR: ${msg}`)
          }
        }
      } else {
        // ── Legacy single-repo ──────────────────────────────────────
        const wt = worktree_path || `/repos/${env_slug}/sessions/${session_id}`
        try {
          const out = await createWorktree({
            slug: env_slug,
            alias: session_id,
            base_branch: base_branch || 'main',
            branch_name: worktree_branch || `cappy/${env_slug}/${session_id}`,
            worktree_path: wt,
          })
          outputs.push(out)
          console.log(`[session_server] created legacy worktree ${wt}`)
        } catch (err) {
          const msg = ((err.stdout || '') + (err.stderr || '')).trim() || err.message
          console.error(`[session_server] failed legacy worktree: ${msg}`)
          return json(res, 500, { error: msg })
        }
      }

      return json(res, 200, {
        session_id,
        session_root: session_root || worktree_path,
        output: outputs.join('\n'),
      })
    }

    // DELETE /sessions/:id — remove sessão
    const deleteMatch = pathname.match(/^\/sessions\/([^/]+)$/)
    if (req.method === 'DELETE' && deleteMatch) {
      const session_id = deleteMatch[1]
      const session_root = url.searchParams.get('session_root') || ''
      const worktree_path = url.searchParams.get('worktree_path') || ''
      const env_slug = url.searchParams.get('env_slug') || 'default'
      let repos = []
      try { repos = JSON.parse(url.searchParams.get('repos') || '[]') } catch {}

      await destroySession({ session_root, repos, env_slug, worktree_path })
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
          await execFileAsync('git', ['-C', repoPath, 'fetch', '--all'], { timeout: 120_000 })
          console.log(`[session_server] fetched ${slug}`)
        } else {
          fs.mkdirSync(repoPath, { recursive: true })
          await execFileAsync('git', ['clone', '--branch', default_branch, clone_url, repoPath], {
            env: { ...process.env },
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
