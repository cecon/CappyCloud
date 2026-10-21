'use strict'
// Handler para POST /mcp/configure — grava mcpServers em ~/.openclaude.json.
// É o único arquivo lido: o openclaude o usa como config global (ignora
// CLAUDE_CONFIG_DIR) e o claude_runtime_handler repassa a mesma lista ao Agent
// SDK. Os settings.json não aceitam mcpServers; a chave antiga é removida deles.

const { execFileSync } = require('child_process')
const fs = require('fs')
const path = require('path')

const GITHUB_WRAPPER = 'github-mcp-server-wrapper'

function hasGithubToken(server, env = process.env, ghToken = readGhToken) {
  const serverEnv = server.env || {}
  const fromEnv = [serverEnv.GITHUB_PERSONAL_ACCESS_TOKEN, serverEnv.GITHUB_TOKEN, env.GITHUB_PERSONAL_ACCESS_TOKEN, env.GITHUB_TOKEN]
  return fromEnv.some((value) => String(value || '').trim()) || Boolean(ghToken())
}

function readGhToken() {
  try {
    return execFileSync('gh', ['auth', 'token'], { encoding: 'utf8', timeout: 5000, stdio: ['ignore', 'pipe', 'ignore'] }).trim()
  } catch {
    return ''
  }
}

/**
 * Tira o MCP do GitHub quando não há token: sem ele o servidor encerra na
 * partida e o agente só vê "CONNECTION_CLOSED".
 */
function usableServers(mcpServers, options = {}) {
  const usable = {}
  const skipped = []
  for (const [name, server] of Object.entries(mcpServers || {})) {
    const isGithub = String(server?.command || '').endsWith(GITHUB_WRAPPER)
    if (isGithub && !hasGithubToken(server, options.env, options.ghToken)) {
      skipped.push(name)
      continue
    }
    usable[name] = server
  }
  return { usable, skipped }
}

function readJson(file) {
  try {
    return JSON.parse(fs.readFileSync(file, 'utf8'))
  } catch {
    return null
  }
}

function writeJson(file, value) {
  fs.mkdirSync(path.dirname(file), { recursive: true })
  fs.writeFileSync(file, JSON.stringify(value, null, 2), 'utf8')
}

/** Troca só mcpServers no ~/.openclaude.json; limpa a cópia antiga dos settings. */
function writeMcpConfig(home, mcpServers) {
  const configPath = path.join(home, '.openclaude.json')
  writeJson(configPath, { ...(readJson(configPath) || {}), mcpServers })
  for (const legacy of [path.join(home, '.claude', 'settings.json'), path.join(home, '.openclaude', 'settings.json')]) {
    const current = readJson(legacy)
    if (current && Object.prototype.hasOwnProperty.call(current, 'mcpServers')) {
      delete current.mcpServers
      writeJson(legacy, current)
    }
  }
}

async function tryHandle(req, res, { json, readBody }) {
  if (req.method !== 'POST' || (req.url || '').split('?')[0] !== '/mcp/configure') return false

  try {
    const body = await readBody(req)
    const { usable: mcpServers, skipped } = usableServers(body.mcpServers)
    writeMcpConfig(process.env.HOME || '/root', mcpServers)
    if (skipped.length) console.log(`[session_server] MCP sem token, fora da config: ${skipped.join(', ')}`)
    console.log(`[session_server] MCP config updated: ${Object.keys(mcpServers).join(', ') || '(none)'}`)
    json(res, 200, { updated: true, servers: Object.keys(mcpServers), skipped })
    return true
  } catch (err) {
    json(res, 500, { error: err.message })
    return true
  }
}

module.exports = { tryHandle, usableServers, writeMcpConfig }
