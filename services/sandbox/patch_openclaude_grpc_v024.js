'use strict'

const fs = require('fs')

const SERVER_FILE = '/openclaude/src/grpc/server.ts'
const HELPER_FILES = [
  '/tmp/cappycloud_grpc_helpers_v024.ts',
  '/tmp/cappycloud_grpc_diagnostics_v024.ts',
]
const WORKSPACE_SCOPE_FILE = '/tmp/cappycloud_grpc_workspace_scope_v024.ts'
const READONLY_COMMANDS_FILE = '/tmp/readonly_commands.js'
const ANCHOR = 'const MAX_SESSIONS = 1000'
const STRICT_GUARD = 'function cappycloudValidateToolScope('

function replaceOnce(source, needle, replacement, label) {
  if (!source.includes(needle)) {
    console.log(`[patch_openclaude_grpc_v024] ${label}: needle not found, skipping.`)
    return source
  }
  // Função de substituição: o texto injetado tem `$` (regex) e não pode virar padrão de replace.
  return source.replace(needle, () => replacement)
}

/** readonly_commands.js (CommonJS) embrulhado para viver dentro do server.ts. */
function readOnlyCommandsBlock(readonlySource) {
  const body = readonlySource
    .replace(/^'use strict'\s*$/m, '')
    .replace(/^module\.exports\s*=\s*/m, 'return ')
  return `const cappycloudReadOnlyCommands = (() => {\n${body}\n})()`
}

/**
 * O multimodal-grpc-handler.patch já traz um guard que só aceita o worktree da
 * sessão. Renomeia esse guard e injeta o que libera leitura do workspace.
 */
function applyWorkspaceScope(source, workspaceScopeSource, readonlySource) {
  if (source.includes('function cappycloudValidateToolScopeStrict(') || !source.includes(STRICT_GUARD)) {
    return source
  }
  const renamed = source.replace(STRICT_GUARD, 'function cappycloudValidateToolScopeStrict(')
  const block = `${readOnlyCommandsBlock(readonlySource)}\n\n${workspaceScopeSource}`
  return replaceOnce(renamed, ANCHOR, `${ANCHOR}\n\n${block}`, 'workspace scope block')
}

function patchServer(source, helperBlock, workspaceScopeSource, readonlySource) {
  let patched = source
  if (!patched.includes("import fs from 'fs'")) {
    patched = replaceOnce(patched, "import path from 'path'", "import fs from 'fs'\nimport path from 'path'", 'fs import')
  }
  if (!patched.includes('import { getMcpToolsCommandsAndResources }')) {
    patched = replaceOnce(
      patched,
      "import { getBuiltInAgents } from '../tools/AgentTool/builtInAgents.js'",
      "import { getBuiltInAgents } from '../tools/AgentTool/builtInAgents.js'\nimport { getMcpToolsCommandsAndResources } from '../services/mcp/client.js'",
      'mcp import',
    )
  }
  if (!patched.includes(STRICT_GUARD)) {
    patched = replaceOnce(patched, ANCHOR, `${ANCHOR}\n\n${helperBlock}`, 'cappycloud helper block')
    return patched
  }
  return applyWorkspaceScope(patched, workspaceScopeSource, readonlySource)
}

if (require.main === module) {
  const read = (file) => fs.readFileSync(file, 'utf8')
  const patched = patchServer(
    read(SERVER_FILE),
    HELPER_FILES.map(read).join('\n'),
    read(WORKSPACE_SCOPE_FILE),
    read(READONLY_COMMANDS_FILE),
  )
  fs.writeFileSync(SERVER_FILE, patched)
  console.log('[patch_openclaude_grpc_v024] patched src/grpc/server.ts')
}

module.exports = { applyWorkspaceScope, patchServer, readOnlyCommandsBlock }
