'use strict'
//   node --test services/sandbox/tests/mcp_handler.test.js
const test = require('node:test')
const assert = require('node:assert/strict')

const { usableServers } = require('../mcp_handler')

const github = { command: '/usr/local/bin/github-mcp-server-wrapper', env: {} }
const signoz = { command: '/usr/local/bin/signoz-mcp-server' }

test('sem token o MCP do GitHub sai da config e os outros ficam', () => {
  const result = usableServers({ github, signoz }, { env: {}, ghToken: () => '' })
  assert.deepEqual(Object.keys(result.usable), ['signoz'])
  assert.deepEqual(result.skipped, ['github'])
})

test('token no ambiente, no cadastro do MCP ou no gh mantém o GitHub', () => {
  const noGh = () => ''
  assert.deepEqual(usableServers({ github }, { env: { GITHUB_TOKEN: 'x' }, ghToken: noGh }).skipped, [])
  const withEnv = { ...github, env: { GITHUB_PERSONAL_ACCESS_TOKEN: 'x' } }
  assert.deepEqual(usableServers({ github: withEnv }, { env: {}, ghToken: noGh }).skipped, [])
  assert.deepEqual(usableServers({ github }, { env: {}, ghToken: () => 'gho_x' }).skipped, [])
})

const fs = require('fs')
const os = require('os')
const path = require('path')
const { writeMcpConfig } = require('../mcp_handler')

test('grava só no ~/.openclaude.json e tira mcpServers dos settings.json', () => {
  const home = fs.mkdtempSync(path.join(os.tmpdir(), 'cappy-mcp-'))
  const settings = path.join(home, '.claude', 'settings.json')
  fs.mkdirSync(path.dirname(settings), { recursive: true })
  fs.writeFileSync(settings, JSON.stringify({ theme: 'dark', mcpServers: { old: {} } }))
  fs.writeFileSync(path.join(home, '.openclaude.json'), JSON.stringify({ userID: 'u1' }))

  writeMcpConfig(home, { signoz })

  const config = JSON.parse(fs.readFileSync(path.join(home, '.openclaude.json'), 'utf8'))
  assert.deepEqual(config, { userID: 'u1', mcpServers: { signoz } })
  assert.deepEqual(JSON.parse(fs.readFileSync(settings, 'utf8')), { theme: 'dark' })
  assert.equal(fs.existsSync(path.join(home, '.openclaude', 'settings.json')), false)
})
