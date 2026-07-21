'use strict'

const fs = require('fs')

const file = '/openclaude/src/grpc/server.ts'
let source = fs.readFileSync(file, 'utf8')

function replaceOnce(needle, replacement, label) {
  if (!source.includes(needle)) {
    console.log(`[patch_openclaude_grpc_v024] ${label}: needle not found, skipping.`)
    return
  }
  source = source.replace(needle, replacement)
}

if (!source.includes("import fs from 'fs'")) {
  replaceOnce("import path from 'path'", "import fs from 'fs'\nimport path from 'path'", 'fs import')
}

if (!source.includes("import { getMcpToolsCommandsAndResources }")) {
  replaceOnce(
    "import { getBuiltInAgents } from '../tools/AgentTool/builtInAgents.js'",
    "import { getBuiltInAgents } from '../tools/AgentTool/builtInAgents.js'\nimport { getMcpToolsCommandsAndResources } from '../services/mcp/client.js'",
    'mcp import',
  )
}

const helperBlock = [
  '/tmp/cappycloud_grpc_helpers_v024.ts',
  '/tmp/cappycloud_grpc_diagnostics_v024.ts',
]
  .map(path => fs.readFileSync(path, 'utf8'))
  .join('\n')

if (!source.includes('function cappycloudValidateToolScope')) {
  replaceOnce(
    'const MAX_SESSIONS = 1000',
    `const MAX_SESSIONS = 1000\n\n${helperBlock}`,
    'cappycloud helper block',
  )
}

fs.writeFileSync(file, source)
console.log('[patch_openclaude_grpc_v024] patched src/grpc/server.ts')
