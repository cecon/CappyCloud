'use strict'
// Handler para POST /mcp/configure — persiste mcpServers em ~/.claude/settings.json

const fs = require('fs')
const path = require('path')

async function tryHandle(req, res, { json, readBody }) {
  if (req.method !== 'POST' || (req.url || '').split('?')[0] !== '/mcp/configure') return false
  
  try {
    const body = await readBody(req)
    const mcpServers = body.mcpServers || {}
    const settingsPath = process.env.HOME
      ? `${process.env.HOME}/.claude/settings.json`
      : '/root/.claude/settings.json'
    
    let current = {}
    try { current = JSON.parse(fs.readFileSync(settingsPath, 'utf8')) } catch {}
    current.mcpServers = mcpServers
    fs.mkdirSync(path.dirname(settingsPath), { recursive: true })
    fs.writeFileSync(settingsPath, JSON.stringify(current, null, 2), 'utf8')
    console.log(`[session_server] MCP config updated: ${Object.keys(mcpServers).join(', ') || '(none)'}`)
    json(res, 200, { updated: true, servers: Object.keys(mcpServers) })
    return true
  } catch (err) {
    json(res, 500, { error: err.message })
    return true
  }
}

module.exports = { tryHandle }
