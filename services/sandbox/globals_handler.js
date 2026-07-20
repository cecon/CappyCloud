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

async function tryHandle(req, res, { json, readBody }) {
  if (req.method !== 'POST' || (req.url || '').split('?')[0] !== '/globals/configure') {
    return false
  }

  try {
    const body = await readBody(req)
    const home = process.env.HOME || '/root'
    const updated = {}
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

module.exports = { tryHandle }
