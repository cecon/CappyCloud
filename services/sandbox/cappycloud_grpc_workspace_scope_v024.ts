// Guard de escopo com o layout de workspace (injetado por patch_openclaude_grpc_v024.js).
// O multimodal-grpc-handler.patch já define um guard que só aceita o worktree da
// sessão; o patch renomeia esse para cappycloudValidateToolScopeStrict e este
// arquivo decide quando liberar: leitura dos repos/conhecimento do workspace,
// igual ao claude_runtime_mapper.js do runtime Claude CLI.
// Sem anotações de tipo: o mesmo texto roda no build (bun) e nos testes (node).

const CAPPYCLOUD_WORKSPACE_READ_TOOLS = new Set(['Read', 'Grep', 'Glob', 'LS', 'LSP'])
const CAPPYCLOUD_WORKSPACE_SESSION_PATTERN = /^(\/repos\/workspaces\/[a-z0-9][a-z0-9-]{1,62})\/sessions\/[^/]+$/
const CAPPYCLOUD_WORKSPACE_SHARED = ['knowledge', 'memory', '.claude', 'repos', 'CLAUDE.md']

function cappycloudWorkspaceRoots(worktree) {
  const match = path.resolve(worktree || '/').match(CAPPYCLOUD_WORKSPACE_SESSION_PATTERN)
  return match ? CAPPYCLOUD_WORKSPACE_SHARED.map((entry) => `${match[1]}/${entry}`) : []
}

function cappycloudInsideAny(roots, candidate) {
  return roots.some((root) => cappycloudIsInsideWorktree(root, candidate))
}

function cappycloudWorkspaceAllows(toolName, input, worktree) {
  const roots = cappycloudWorkspaceRoots(worktree)
  if (!roots.length || !input || typeof input !== 'object') {
    return false
  }
  const allowed = [worktree, ...roots]
  if (CAPPYCLOUD_WORKSPACE_READ_TOOLS.has(toolName)) {
    return cappycloudCollectPathInputs(input).every((rawPath) => {
      const resolved = cappycloudResolveToolPath(worktree, rawPath)
      return !resolved || cappycloudInsideAny(allowed, resolved)
    })
  }
  const command = input.command
  if (toolName !== 'Bash' || typeof command !== 'string') {
    return false
  }
  if (/(^|[\s;&|])cd\s+\.\.(?:\/|\s|$)/.test(command) || /(^|[\s"'=])\.\.(?:\/|$)/.test(command)) {
    return false
  }
  if (!cappycloudReadOnlyCommands.isReadOnlyCommand(command)) {
    return false
  }
  return cappycloudExtractRepoPaths(command).every((rawPath) => {
    const resolved = cappycloudResolveToolPath(worktree, rawPath)
    return !resolved || cappycloudInsideAny(allowed, resolved)
  })
}

const CAPPYCLOUD_WORKSPACE_READONLY_HINT =
  ' Somente leitura: nos repos do workspace o Bash aceita só comandos de leitura (rg, grep, find, cat, sed -n, head, ls, jq, base64, git log/show), sem python/node e sem gravar arquivo. Para trechos de arquivo grande use Read com offset/limit ou Grep.'

// Bloqueio de Bash que só toca repos do workspace: explica o motivo, senão o
// agente repete o comando e o openclaude encerra por "repeated tool failures".
function cappycloudWorkspaceHint(toolName, input, worktree) {
  const roots = cappycloudWorkspaceRoots(worktree)
  if (toolName !== 'Bash' || !roots.length || !input || typeof input.command !== 'string') {
    return ''
  }
  const touchesWorkspace = cappycloudExtractRepoPaths(input.command).some((rawPath) => {
    const resolved = cappycloudResolveToolPath(worktree, rawPath)
    return resolved && cappycloudInsideAny(roots, resolved)
  })
  return touchesWorkspace ? CAPPYCLOUD_WORKSPACE_READONLY_HINT : ''
}

function cappycloudValidateToolScope(toolName, input, worktree, ...rest) {
  const blocked = cappycloudValidateToolScopeStrict(toolName, input, worktree, ...rest)
  if (!blocked) {
    return blocked
  }
  if (cappycloudWorkspaceAllows(toolName, input, worktree)) {
    return null
  }
  return blocked + cappycloudWorkspaceHint(toolName, input, worktree)
}
