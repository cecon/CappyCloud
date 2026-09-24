'use strict'
// Materializa workspaces no sandbox (enfileirado pela API via watchdog):
//
//   POST   /workspaces/sync   {slug, claude_md, repos:[{alias, slug}]}
//   DELETE /workspaces/:slug  (409 se houver sessões dentro)
//
// Estrutura:  /repos/workspaces/<slug>/
//   CLAUDE.md               ← do workspace (o Claude CLI herda nas sessões abaixo)
//   .claude/{skills,agents,commands}/
//   knowledge/  memory/  sessions/
//   repos/<alias> -> /repos/<repo-slug>   (link para o clone do catálogo, sem duplicar)

const fs = require('fs')
const path = require('path').posix

const WORKSPACE_SLUG = /^[a-z0-9][a-z0-9-]{1,62}$/
const SAFE_NAME = /^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/
const SUBDIRS = ['.claude/skills', '.claude/agents', '.claude/commands', 'knowledge', 'memory', 'repos', 'sessions']

function workspaceRoot(slug, reposRoot) {
  if (!WORKSPACE_SLUG.test(String(slug || ''))) throw new Error(`workspace slug inválido: ${slug}`)
  return path.join(reposRoot, 'workspaces', slug)
}

/** Cria/atualiza a árvore do workspace. Só mexe em links dentro de repos/, nunca em clones. */
function syncWorkspace({ slug, claude_md = '', repos = [] }, { reposRoot = '/repos' } = {}) {
  const root = workspaceRoot(slug, reposRoot)
  const desired = new Map()
  for (const repo of repos) {
    const alias = String(repo.alias || repo.slug || '')
    const repoSlug = String(repo.slug || '')
    if (!SAFE_NAME.test(alias) || !SAFE_NAME.test(repoSlug)) throw new Error(`repo inválido: ${alias}/${repoSlug}`)
    desired.set(alias, path.join(reposRoot, repoSlug))
  }

  for (const dir of SUBDIRS) fs.mkdirSync(path.join(root, dir), { recursive: true })

  const claudeMd = path.join(root, 'CLAUDE.md')
  if (String(claude_md).trim()) fs.writeFileSync(claudeMd, claude_md, 'utf8')
  else fs.rmSync(claudeMd, { force: true })

  const reposDir = path.join(root, 'repos')
  for (const entry of fs.readdirSync(reposDir, { withFileTypes: true })) {
    if (!entry.isSymbolicLink()) continue // pasta real em repos/ não é nossa: não toca
    const linkPath = path.join(reposDir, entry.name)
    if (desired.get(entry.name) !== fs.readlinkSync(linkPath)) fs.unlinkSync(linkPath)
  }
  const result = []
  for (const [alias, target] of desired) {
    const linkPath = path.join(reposDir, alias)
    if (!fs.existsSync(linkPath) && !isSymlink(linkPath)) fs.symlinkSync(target, linkPath)
    result.push({ alias, target, cloned: fs.existsSync(path.join(target, '.git')) })
  }
  return { root, repos: result }
}

function isSymlink(p) {
  try { return fs.lstatSync(p).isSymbolicLink() } catch { return false }
}

/** Remove o workspace; recusa se ainda houver sessões (worktrees) dentro. */
function removeWorkspace(slug, { reposRoot = '/repos' } = {}) {
  const root = workspaceRoot(slug, reposRoot)
  if (!fs.existsSync(root)) return { removed: false, reason: 'não existe' }
  const sessionsDir = path.join(root, 'sessions')
  const sessions = fs.existsSync(sessionsDir) ? fs.readdirSync(sessionsDir) : []
  if (sessions.length) return { removed: false, reason: `${sessions.length} sessão(ões) ativa(s)`, busy: true }
  // rm só remove os links de repos/, nunca os clones do catálogo.
  fs.rmSync(root, { recursive: true, force: true })
  return { removed: true }
}

async function tryHandle(req, res, { json, readBody }) {
  const pathname = (req.url || '').split('?')[0]
  if (req.method === 'POST' && pathname === '/workspaces/sync') {
    try {
      const result = syncWorkspace(await readBody(req))
      console.log(`[workspace] sync ${result.root}: ${result.repos.map((r) => r.alias).join(', ') || '(sem repos)'}`)
      json(res, 200, result)
    } catch (err) {
      json(res, 400, { error: err.message })
    }
    return true
  }
  const match = pathname.match(/^\/workspaces\/([^/]+)$/)
  if (req.method === 'DELETE' && match) {
    try {
      const result = removeWorkspace(decodeURIComponent(match[1]))
      json(res, result.busy ? 409 : 200, result)
    } catch (err) {
      json(res, 400, { error: err.message })
    }
    return true
  }
  return false
}

module.exports = { removeWorkspace, syncWorkspace, tryHandle }
