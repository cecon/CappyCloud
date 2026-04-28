'use strict'
// ──────────────────────────────────────────────────────────────
// POST /worktree/* — ls-files, read-file, diff, push, current-branch
// Exporta `tryHandle(req, res, { json, readBody })` → true se tratou.
// ──────────────────────────────────────────────────────────────

const fs = require('fs')
const path = require('path')
const { execFile } = require('child_process')
const { promisify } = require('util')

const execFileAsync = promisify(execFile)

function resolveSafeWorktree(raw) {
  if (!raw || typeof raw !== 'string') {
    throw new Error('worktree_path é obrigatório')
  }
  const resolved = path.resolve(raw.trim())
  if (!resolved.startsWith('/repos/sessions/')) {
    throw new Error('worktree_path tem de estar em /repos/sessions/')
  }
  return resolved
}

function resolveSafeFileInWorktree(worktreeRaw, relPath) {
  if (!relPath || typeof relPath !== 'string') {
    throw new Error('path é obrigatório')
  }
  if (relPath.includes('..') || path.isAbsolute(relPath)) {
    throw new Error('path inválido')
  }
  const wt = resolveSafeWorktree(worktreeRaw)
  const full = path.resolve(path.join(wt, relPath))
  const prefix = wt.endsWith('/') ? wt : wt + '/'
  if (full !== wt && !full.startsWith(prefix)) {
    throw new Error('path fora do worktree')
  }
  return full
}

/**
 * Tenta tratar POST /worktree/*. Retorna true se tratou.
 * @param {import('http').IncomingMessage} req
 * @param {import('http').ServerResponse} res
 * @param {{ json: Function, readBody: Function }} helpers
 */
async function tryHandle(req, res, { json, readBody }) {
  if (req.method !== 'POST' || !req.url) return false
  const pathname = new URL(req.url, 'http://localhost').pathname

  if (pathname === '/worktree/ls-files') {
    const body = await readBody(req)
    try {
      const wt = resolveSafeWorktree(body.worktree_path)
      const { stdout } = await execFileAsync('git', ['-C', wt, 'ls-files'], {
        timeout: 120_000,
        maxBuffer: 50 * 1024 * 1024,
      })
      const raw = ((stdout || '') + '').trimEnd()
      const files = raw.split(/\r?\n/).map(l => l.trim()).filter(Boolean)
      await json(res, 200, { worktree_path: wt, files })
    } catch (err) {
      const detail = (err.stderr && String(err.stderr)) || err.message || String(err)
      console.error('[worktree/ls-files]', detail)
      await json(res, 500, { error: 'git ls-files falhou', detail })
    }
    return true
  }

  if (pathname === '/worktree/read-file') {
    const body = await readBody(req)
    try {
      const full = resolveSafeFileInWorktree(body.worktree_path, body.path || '')
      const content = fs.readFileSync(full, 'utf8')
      await json(res, 200, { path: body.path, content })
    } catch (err) {
      await json(res, (err.code === 'ENOENT' ? 404 : 500), {
        error: err.code === 'ENOENT' ? 'Ficheiro não encontrado' : 'Erro ao ler ficheiro',
        detail: err.message,
      })
    }
    return true
  }

  if (pathname === '/worktree/diff') {
    const body = await readBody(req)
    const baseBranch = (body.base_branch || 'main').trim()
    try {
      const wt = resolveSafeWorktree(body.worktree_path)
      const { stdout } = await execFileAsync(
        'git',
        ['-C', wt, 'diff', `${baseBranch}..HEAD`],
        { timeout: 120_000, maxBuffer: 50 * 1024 * 1024 },
      )
      const diffText = ((stdout || '') + '').toString()
      await json(res, 200, { diff_text: diffText, base_branch: baseBranch })
    } catch (err) {
      const detail = (err.stderr && String(err.stderr)) || err.message || String(err)
      console.error('[worktree/diff]', detail)
      await json(res, 500, { error: 'git diff falhou', detail })
    }
    return true
  }

  if (pathname === '/worktree/push-origin-head') {
    const body = await readBody(req)
    try {
      const wt = resolveSafeWorktree(body.worktree_path)
      await execFileAsync(
        'git',
        ['-C', wt, 'push', '--set-upstream', 'origin', 'HEAD', '--quiet'],
        { timeout: 120_000, maxBuffer: 10 * 1024 * 1024 },
      ).catch((e) => {
        console.warn('[worktree/push-origin-head]', e.message || e)
      })
      await json(res, 200, { ok: true })
    } catch (err) {
      await json(res, 500, { error: 'push falhou', detail: err.message })
    }
    return true
  }

  if (pathname === '/worktree/current-branch') {
    const body = await readBody(req)
    try {
      const wt = resolveSafeWorktree(body.worktree_path)
      const { stdout } = await execFileAsync(
        'git',
        ['-C', wt, 'rev-parse', '--abbrev-ref', 'HEAD'],
        { timeout: 60_000, maxBuffer: 1024 * 1024 },
      )
      const branch = ((stdout || '') + '').toString().trim()
      if (!branch) {
        await json(res, 500, { error: 'branch vazio' })
      } else {
        await json(res, 200, { branch })
      }
    } catch (err) {
      const detail = (err.stderr && String(err.stderr)) || err.message || String(err)
      await json(res, 500, { error: 'rev-parse falhou', detail })
    }
    return true
  }

  return false
}

module.exports = { tryHandle }
