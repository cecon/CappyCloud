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
//   POST   /git/ls-remote-branches → git ls-remote --heads (URL com ou sem PAT)
//   POST   /git/origin-head-branch → default local (symbolic-ref)
//   POST   /git/branch-r           → git branch -r no clone /repos/...
//   GET    /health                 → liveness probe
// ──────────────────────────────────────────────────────────────

const http = require('http')
const fs = require('fs')
const path = require('path')
const { execFile, execFileSync } = require('child_process')
const { promisify } = require('util')

const gitHandlers = require('./git_handlers')
const repoHandlers = require('./repo_handlers')

const execFileAsync = promisify(execFile)
const PORT = parseInt(process.env.SESSION_SERVER_PORT || '8080', 10)

/**
 * Injeta tokens de autenticação na URL git antes de clonar/fazer fetch.
 * Prioridade: token explícito (do payload) > env var (DEVOPS_TOKEN/GITHUB_TOKEN).
 * @param {string} url
 * @param {string} explicitToken - PAT recebido no payload (do banco)
 * @param {string} providerType - github | azure_devops
 * @returns {string}
 */
function injectToken(url, explicitToken = '', providerType = '') {
  const devopsToken = explicitToken && (providerType === 'azure_devops' || /dev\.azure\.com/.test(url))
    ? explicitToken
    : (process.env.DEVOPS_TOKEN || '')
  const githubToken = explicitToken && (providerType === 'github' || /github\.com/.test(url))
    ? explicitToken
    : (process.env.GITHUB_TOKEN || '')
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
  const gitDir = path.join(worktree_path, '.git')
  if (!fs.existsSync(gitDir)) {
    throw new Error(`worktree não foi criado em ${worktree_path}`)
  }
  return (stdout + stderr).trim()
}

// ── Remove session_root e prune worktrees ─────────────────────
async function destroySession({ session_root, repos }) {
  if (session_root) {
    await execFileAsync('rm', ['-rf', session_root], { timeout: 30_000 }).catch(() => {})
  }

  // repos pode vir como array, string JSON ou null/undefined.
  let arr = repos
  if (typeof arr === 'string') {
    try { arr = JSON.parse(arr) } catch { arr = [] }
  }
  if (!Array.isArray(arr)) arr = []
  const slugs = new Set(arr.map(r => r && r.slug).filter(Boolean))
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
      const repos_created = []

      fs.mkdirSync(session_root, { recursive: true })

      // CLAUDE.md na raiz da sessão: só se não houver instruções no próprio repo
      // (cada worktree pode ter o seu CLAUDE.md / AGENTS.md). Aqui é a raiz
      // multi-repo, fica como descrição neutra do ambiente.
      if (
        !fs.existsSync(path.join(session_root, 'CLAUDE.md')) &&
        !fs.existsSync(path.join(session_root, 'AGENTS.md')) &&
        fs.existsSync('/app/CLAUDE.md')
      ) {
        fs.copyFileSync('/app/CLAUDE.md', path.join(session_root, 'CLAUDE.md'))
      }

      for (const repo of repos) {
        const { slug, alias, base_branch: rb, branch_name, clone_url: rc } = repo
        if (!slug || !alias) continue
        const wt_path = path.join(session_root, alias)
        const resolved_branch = branch_name || `cappy/${slug}/${session_id}-${alias}`
        try {
          const out = await createWorktree({
            slug,
            alias,
            base_branch: rb || 'main',
            branch_name: resolved_branch,
            worktree_path: wt_path,
            clone_url: rc || '',
          })
          outputs.push(`[${alias}] ${out}`)
          repos_created.push({ alias, branch_name: resolved_branch, worktree_path: wt_path })
          console.log(`[session_server] created worktree ${wt_path} on branch ${resolved_branch}`)
        } catch (err) {
          const msg = ((err.stdout || '') + (err.stderr || '')).trim() || err.message
          console.error(`[session_server] failed worktree ${wt_path}: ${msg}`)
          outputs.push(`[${alias}] ERROR: ${msg}`)
          repos_created.push({ alias, branch_name: resolved_branch, worktree_path: wt_path, error: msg })
        }
      }

      const errors = repos_created.filter(r => r.error)
      if (errors.length > 0) {
        return json(res, 500, {
          session_id,
          session_root,
          repos_created,
          error: 'failed to create one or more repo worktrees',
          output: outputs.join('\n'),
        })
      }

      return json(res, 200, {
        session_id,
        session_root,
        repos_created,
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

    // /repos/clone (POST) e /repos/:slug (DELETE)
    if (await repoHandlers.tryHandle(req, res, { json, readBody, injectToken })) {
      return
    }

    // /git/* handlers (ls-remote-branches, origin-head-branch, branch-r)
    if (await gitHandlers.tryHandle(req, res, { json, readBody, injectToken })) {
      return
    }

    // GET /skills/search?q=...&agent_id=... — proxy para a API CappyCloud
    // O LLM (openclaude) usa este endpoint via curl/Bash para fazer RAG por demanda.
    if (req.method === 'GET' && pathname === '/skills/search') {
      const q = url.searchParams.get('q') || ''
      const agentId = url.searchParams.get('agent_id') || ''
      const limit = url.searchParams.get('limit') || '5'
      if (!q) return json(res, 400, { error: 'q is required' })

      const apiHost = process.env.API_HOST || 'cappycloud-api'
      const apiPort = process.env.API_PORT_INTERNAL || '8080'
      const internalToken = process.env.INTERNAL_API_TOKEN || ''
      const params = new URLSearchParams({ q, limit })
      if (agentId) params.set('agent_id', agentId)
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
