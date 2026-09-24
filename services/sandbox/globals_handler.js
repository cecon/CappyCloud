'use strict'
// Handler para POST /globals/configure — materializa skills e agents globais
// sem depender de Docker socket no container da API.

const fs = require('fs')
const path = require('path')

const SAFE_NAME = /^[a-zA-Z0-9][a-zA-Z0-9._-]{0,127}$/

function safeName(raw, kind) {
  const name = String(raw || '').trim()
  if (!SAFE_NAME.test(name) || name.includes('..') || name.includes('/')) {
    throw new Error(`${kind} inválido: ${name || '(vazio)'}`)
  }
  return name
}

function resetDir(dir) {
  fs.rmSync(dir, { recursive: true, force: true })
  fs.mkdirSync(dir, { recursive: true })
}

function writeSkills(home, skills) {
  const dir = path.join(home, '.claude', 'skills')
  resetDir(dir)
  for (const item of skills) {
    const name = safeName(item.name, 'skill')
    const markdown = String(item.markdown || '')
    const skillDir = path.join(dir, name)
    fs.mkdirSync(skillDir, { recursive: true })
    fs.writeFileSync(path.join(skillDir, 'SKILL.md'), markdown, 'utf8')
  }
  return skills.map(item => item.name)
}

function writeAgents(home, agents) {
  const dir = path.join(home, '.claude', 'agents')
  resetDir(dir)
  for (const item of agents) {
    const name = safeName(item.name, 'agent')
    const markdown = String(item.markdown || '')
    fs.writeFileSync(path.join(dir, `${name}.md`), markdown, 'utf8')
  }
  return agents.map(item => item.name)
}

// Memória do usuário dos dois runtimes: o Claude CLI lê ~/.claude/CLAUDE.md
// (CLAUDE_CONFIG_DIR) e o openclaude ~/.openclaude/CLAUDE.md. O conteúdo é a
// base da imagem (/app/CLAUDE.md) mais as instruções extras do sandbox,
// guardadas no volume para a base ser reaplicada quando a imagem mudar.
const BASE_CLAUDE_MD = '/app/CLAUDE.md'
const EXTRA_FILE = 'cappycloud-claude-extra.md'

function claudeMdTargets(home) {
  return [path.join(home, '.claude', 'CLAUDE.md'), path.join(home, '.openclaude', 'CLAUDE.md')]
}

function readText(file) {
  try {
    return fs.readFileSync(file, 'utf8')
  } catch {
    return ''
  }
}

function composeClaudeMd(base, extra) {
  const parts = [base.trim()]
  if (extra.trim()) parts.push(`## Instruções deste sandbox\n\n${extra.trim()}`)
  const content = parts.filter(Boolean).join('\n\n')
  return content ? `${content}\n` : ''
}

/** Regrava a memória do usuário. `extra` undefined = mantém as extras salvas. */
function writeClaudeMd(home, extra, basePath = BASE_CLAUDE_MD) {
  const extraPath = path.join(home, '.claude', EXTRA_FILE)
  if (extra !== undefined) {
    fs.mkdirSync(path.dirname(extraPath), { recursive: true })
    fs.writeFileSync(extraPath, String(extra || ''), 'utf8')
  }
  const content = composeClaudeMd(readText(basePath), readText(extraPath))
  for (const target of claudeMdTargets(home)) {
    if (!content) {
      fs.rmSync(target, { force: true })
      continue
    }
    fs.mkdirSync(path.dirname(target), { recursive: true })
    fs.writeFileSync(target, content, 'utf8')
  }
}

async function tryHandle(req, res, { json, readBody }) {
  if (req.method !== 'POST' || (req.url || '').split('?')[0] !== '/globals/configure') {
    return false
  }

  try {
    const body = await readBody(req)
    const home = process.env.HOME || '/root'
    const updated = {}
    if (Object.prototype.hasOwnProperty.call(body, 'claude_md')) {
      writeClaudeMd(home, body.claude_md)
      updated.claude_md = true
    }
    if (Array.isArray(body.skills)) {
      updated.skills = writeSkills(home, body.skills)
    }
    if (Array.isArray(body.agents)) {
      updated.agents = writeAgents(home, body.agents)
    }
    console.log('[session_server] globals updated:', JSON.stringify(updated))
    json(res, 200, { updated: true, ...updated })
    return true
  } catch (err) {
    json(res, 500, { error: err.message })
    return true
  }
}

module.exports = { tryHandle, writeClaudeMd }
