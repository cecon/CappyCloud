#!/usr/bin/env node
'use strict'
// Session Server — Sidecar para gerenciar sessões multi-repo e Git.
// POST /sessions → cria worktrees; DELETE /sessions/:id → remove.
// Proxy para git-handlers, repo-handlers, task-handler e worktree-handlers.

const http = require('http')
const fs = require('fs')
const path = require('path')
const { execFile, execFileSync } = require('child_process')
const { promisify } = require('util')

const gitHandlers = require('./git_handlers')
const repoHandlers = require('./repo_handlers')
const taskHandler = require('./task_handler')
const worktreeHandlers = require('./worktree_handlers')

const execFileAsync = promisify(execFile)
const PORT = parseInt(process.env.SESSION_SERVER_PORT || '8080', 10)

function injectToken(url, explicitToken = '', providerType = '') {
  const dt = explicitToken && (providerType === 'azure_devops' || /dev\.azure\.com/.test(url)) ? explicitToken : (process.env.DEVOPS_TOKEN || '')
  const gt = explicitToken && (providerType === 'github' || /github\.com/.test(url)) ? explicitToken : (process.env.GITHUB_TOKEN || '')
  let res = url
  if (dt && res.includes('dev.azure.com')) res = res.replace(/https:\/\/([^@]*@)?dev\.azure\.com/, `https://pat:${dt}@dev.azure.com`)
  if (gt && res.includes('github.com')) res = res.replace(/https:\/\/([^@]*@)?github\.com/, `https://x-token:${gt}@github.com`)
  return res
}

function json(res, status, body) {
  const p = JSON.stringify(body); res.writeHead(status, { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(p) }); res.end(p)
}
function readBody(req) {
  return new Promise((resolve, reject) => {
    let d = ''; req.on('data', c => { d += c }); req.on('end', () => { try { resolve(d ? JSON.parse(d) : {}) } catch { reject(new Error('Invalid JSON')) } }); req.on('error', reject)
  })
}

// ── Cria um worktree via session_start.sh ──────────────────────
async function createWorktree({ slug, alias, base_branch, branch_name, worktree_path, clone_url = '' }) {
  const args = [slug, alias, worktree_path, base_branch || '', branch_name || '', clone_url]
  const { stdout, stderr } = await execFileAsync('/session_start.sh', args, { env: { ...process.env }, timeout: 60_000 })
  if (!fs.existsSync(path.join(worktree_path, '.git'))) throw new Error(`worktree não foi criado em ${worktree_path}`)
  return (stdout + stderr).trim()
}
async function destroySession({ session_root, repos }) {
  if (session_root) await execFileAsync('rm', ['-rf', session_root], { timeout: 30_000 }).catch(() => {})
  let arr = Array.isArray(repos) ? repos : []; if (typeof repos === 'string') try { arr = JSON.parse(repos) } catch {}
  const slugs = new Set((Array.isArray(arr) ? arr : []).map(r => r && r.slug).filter(Boolean))
  for (const slug of slugs) await execFileAsync('git', ['-C', `/repos/${slug}`, 'worktree', 'prune'], { timeout: 30_000 }).catch(() => {})
}

// ── HTTP server ───────────────────────────────────────────────
const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, `http://localhost:${PORT}`)
  const pathname = url.pathname

  try {
    // GET /health
    if (req.method === 'GET' && pathname === '/health') return json(res, 200, { status: 'ok' })

    // POST /sessions — cria sessão multi-repo
    if (req.method === 'POST' && pathname === '/sessions') {
      const { session_id, repos = [], session_root = '' } = await readBody(req)
      if (!session_id || !session_root) return json(res, 400, { error: 'session_id/root required' })

      const outputs = []
      const repos_created = []

      fs.mkdirSync(session_root, { recursive: true })

      if (!fs.existsSync(path.join(session_root, 'CLAUDE.md')) && !fs.existsSync(path.join(session_root, 'AGENTS.md')) && fs.existsSync('/app/CLAUDE.md')) {
        fs.copyFileSync('/app/CLAUDE.md', path.join(session_root, 'CLAUDE.md'))
      }

      for (const r of repos) {
        const { slug, alias, base_branch: rb, branch_name, clone_url: rc } = r; if (!slug || !alias) continue
        const wt_path = path.join(session_root, alias), b = branch_name || `cappy/${slug}/${session_id}-${alias}`
        try {
          const out = await createWorktree({ slug, alias, base_branch: rb || 'main', branch_name: b, worktree_path: wt_path, clone_url: rc || '' })
          outputs.push(`[${alias}] ${out}`); repos_created.push({ alias, branch_name: b, worktree_path: wt_path })
        } catch (err) {
          const msg = ((err.stdout || '') + (err.stderr || '')).trim() || err.message
          outputs.push(`[${alias}] ERROR: ${msg}`); repos_created.push({ alias, branch_name: b, worktree_path: wt_path, error: msg })
        }
      }
      if (repos.length > 1 && repos_created.length > 0 && !repos_created[0].error) {
        const firstWt = repos_created[0].worktree_path, claudeSrc = path.join(session_root, 'CLAUDE.md'), claudeDst = path.join(firstWt, 'CLAUDE.md')
        if (fs.existsSync(claudeSrc) && !fs.existsSync(claudeDst)) try { fs.copyFileSync(claudeSrc, claudeDst) } catch {}
      }
      const errs = repos_created.filter(r => r.error)
      return json(res, 200, { session_id, session_root, repos_created, output: outputs.join('\n'), ...(errs.length > 0 ? { warnings: errs.map(r => `[${r.alias}] ${r.error}`) } : {}) })
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

    // DELETE /sessions/:id/worktree/:alias — remove a single worktree from a session
    const deleteWorktreeMatch = pathname.match(/^\/sessions\/([^/]+)\/worktree\/([^/]+)$/)
    if (req.method === 'DELETE' && deleteWorktreeMatch) {
      const session_id = deleteWorktreeMatch[1]
      const alias = deleteWorktreeMatch[2]
      const session_root = url.searchParams.get('session_root') || ''
      const slug = url.searchParams.get('slug') || alias

      const worktreePath = session_root
        ? path.join(session_root, alias)
        : `/repos/sessions/${session_id}/${alias}`

      try {
        // Remove the worktree directory
        await execFileAsync('rm', ['-rf', worktreePath], { timeout: 30_000 })
        // Prune worktree metadata from the bare repo
        await execFileAsync(
          'git', ['-C', `/repos/${slug}`, 'worktree', 'prune'],
          { timeout: 30_000 }
        ).catch(() => {})
        console.log(`[session_server] removed worktree ${alias} (${worktreePath}) from session ${session_id}`)
        return json(res, 200, { deleted: true, session_id, alias, worktree_path: worktreePath })
      } catch (err) {
        console.error(`[session_server] failed to remove worktree ${alias}: ${err.message}`)
        return json(res, 500, { error: err.message })
      }
    }

    // /repos/clone (POST) e /repos/:slug (DELETE)
    if (await repoHandlers.tryHandle(req, res, { json, readBody, injectToken })) {
      return
    }

    // /git/* handlers (ls-remote-branches, origin-head-branch, branch-r)
    if (await gitHandlers.tryHandle(req, res, { json, readBody, injectToken })) {
      return
    }

    // POST /task — delega sub-agente ao OpenRouter (ver task_handler.js)
    if (await taskHandler.tryHandle(req, res, { json, readBody })) return

    // GET /skills/search?q=... — proxy para a API CappyCloud
    // O LLM (openclaude) usa este endpoint via curl/Bash para fazer RAG por demanda.
    if (req.method === 'GET' && pathname === '/skills/search') {
      const q = url.searchParams.get('q') || ''
      const limit = url.searchParams.get('limit') || '5'
      if (!q) return json(res, 400, { error: 'q is required' })

      const apiHost = process.env.API_HOST || 'cappycloud-api'
      const apiPort = process.env.API_PORT_INTERNAL || '8080'
      const internalToken = process.env.INTERNAL_API_TOKEN || ''
      const params = new URLSearchParams({ q, limit })
      const apiUrl = `http://${apiHost}:${apiPort}/api/skills/_search/internal?${params}`
      try {
        const resp = await fetch(apiUrl, {
          headers: internalToken ? { 'X-Internal-Token': internalToken } : {},
        })
        const text = await resp.text()
        if (resp.status >= 400) {
          return json(res, resp.status, { error: 'API error', detail: text.slice(0, 300) })
        }
        res.writeHead(200, { 'Content-Type': 'application/json' })
        return res.end(text)
      } catch (err) {
        return json(res, 502, { error: 'API unreachable', detail: err.message })
      }
    }

    if (await worktreeHandlers.tryHandle(req, res, { json, readBody })) return

    // POST /git-auth — reconfigura credenciais git (token actualizado no DB)
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
