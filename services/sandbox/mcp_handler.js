'use strict'
// Handler para POST /mcp/configure — persiste mcpServers na configuração lida
// pelo openclaude e mantém o arquivo legado para inspeção humana.

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

async function tryHandle(req, res, { json, readBody }) {
  if (req.method !== 'POST' || (req.url || '').split('?')[0] !== '/mcp/configure') return false

  try {
    const body = await readBody(req)
    const { usable: mcpServers, skipped } = usableServers(body.mcpServers)
    const home = process.env.HOME || '/root'
    const settingsPaths = [
      `${home}/.openclaude.json`,
      `${home}/.claude/settings.json`,
      `${home}/.openclaude/settings.json`,
    ]

    for (const settingsPath of settingsPaths) {
      let current = {}
      try { current = JSON.parse(fs.readFileSync(settingsPath, 'utf8')) } catch {}
      current.mcpServers = mcpServers
      fs.mkdirSync(path.dirname(settingsPath), { recursive: true })
      fs.writeFileSync(settingsPath, JSON.stringify(current, null, 2), 'utf8')
    }
    if (skipped.length) console.log(`[session_server] MCP sem token, fora da config: ${skipped.join(', ')}`)
    console.log(`[session_server] MCP config updated: ${Object.keys(mcpServers).join(', ') || '(none)'}`)
    json(res, 200, { updated: true, servers: Object.keys(mcpServers), skipped })
    return true
  } catch (err) {
    json(res, 500, { error: err.message })
    return true
  }
}

module.exports = { tryHandle, usableServers }
