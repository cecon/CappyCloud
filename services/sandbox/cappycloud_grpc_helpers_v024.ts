const CAPPYCLOUD_PATH_GUARDED_TOOLS = new Set([
  'Read',
  'Write',
  'Edit',
  'Grep',
  'Glob',
  'NotebookEdit',
  'LSP',
  'SendUserMessage',
  'Brief',
])

const CAPPYCLOUD_COMMAND_GUARDED_TOOLS = new Set(['Bash', 'Monitor'])

const CAPPYCLOUD_PERMISSION_MODES = new Set([
  'request_permissions',
  'accept_edits',
  'plan',
  'auto',
  'bypass_permissions',
])

const CAPPYCLOUD_EDIT_TOOLS = new Set(['Write', 'Edit', 'NotebookEdit', 'MultiEdit'])
const CAPPYCLOUD_READ_ONLY_TOOLS = new Set(['Read', 'Grep', 'Glob', 'LS', 'LSP'])
const CAPPYCLOUD_MUTATING_TOOLS = new Set(['Write', 'Edit', 'NotebookEdit', 'MultiEdit', 'Bash'])

type CappycloudPermissionDecision = {
  behavior: 'allow' | 'deny'
  message?: string
}

function cappycloudGrpcString(value: unknown): string {
  return Buffer.from(String(value ?? ''), 'utf8').toString('utf8')
}

function cappycloudPermissionMode(value: unknown): string {
  if (typeof value !== 'string') {
    return 'bypass_permissions'
  }
  const mode = value.trim()
  return CAPPYCLOUD_PERMISSION_MODES.has(mode) ? mode : 'bypass_permissions'
}

function cappycloudPermissionDecision(mode: string, toolName: string): CappycloudPermissionDecision | null {
  if (mode === 'request_permissions') {
    return CAPPYCLOUD_READ_ONLY_TOOLS.has(toolName) ? { behavior: 'allow' } : null
  }
  if (mode === 'accept_edits') {
    return CAPPYCLOUD_EDIT_TOOLS.has(toolName) ? { behavior: 'allow' } : null
  }
  if (mode === 'plan') {
    if (!CAPPYCLOUD_MUTATING_TOOLS.has(toolName)) {
      return null
    }
    return {
      behavior: 'deny',
      message: 'Tool blocked: permission mode "plan" allows planning and read-only inspection only. Switch the session permission mode before editing files or running commands.',
    }
  }
  return { behavior: 'allow' }
}

const CAPPYCLOUD_PATH_INPUT_KEYS = [
  'file_path',
  'path',
  'notebook_path',
  'filePath',
  'team_file_path',
]

const CAPPYCLOUD_PARAMETER_DIR_CACHE = new Map<string, boolean>()

const CAPPYCLOUD_DIAGNOSTIC_LABELS = new Map<string, string>([
  ['user_message', 'Mensagem do usuario'],
  ['conversation_history', 'Historico da conversa'],
  ['attachments', 'Anexos'],
  ['tool_schemas', 'Ferramentas'],
  ['mcp_tool_schemas', 'Ferramentas MCP'],
  ['runtime_context', 'Contexto de runtime'],
  ['other', 'Outros'],
])

type CappycloudDiagnosticCategory = {
  key: string
  label: string
  size_bytes: number
  percentage?: number
}

function cappycloudIsInsideWorktree(worktree: string, candidate: string): boolean {
  const relative = path.relative(worktree, candidate)
  return relative === '' || (!!relative && !relative.startsWith('..') && !path.isAbsolute(relative))
}

function cappycloudResolveToolPath(worktree: string, rawPath: string): string | null {
  const cleaned = rawPath.trim()
  if (!cleaned || cleaned === '.' || cleaned === 'undefined' || cleaned === 'null') {
    return null
  }
  if (/^[a-zA-Z][a-zA-Z0-9+.-]*:\/\//.test(cleaned)) {
    return null
  }
  return path.resolve(path.isAbsolute(cleaned) ? cleaned : path.join(worktree, cleaned))
}

function cappycloudCollectPathInputs(input: unknown): string[] {
  if (!input || typeof input !== 'object') {
    return []
  }
  const record = input as Record<string, unknown>
  const paths: string[] = []
  for (const key of CAPPYCLOUD_PATH_INPUT_KEYS) {
    const value = record[key]
    if (typeof value === 'string') {
      paths.push(value)
    }
  }
  const attachments = record.attachments
  if (Array.isArray(attachments)) {
    for (const attachment of attachments) {
      if (typeof attachment === 'string') {
        paths.push(attachment)
      }
    }
  }
  return paths
}

function cappycloudExtractRepoPaths(command: string): string[] {
  const paths: string[] = []
  const repoPathPattern = /(?:^|[\s"'=:(])((?:\/repos\/)[^\s"'`;&|)<>]+)/g
  for (const match of command.matchAll(repoPathPattern)) {
    const rawPath = match[1]?.replace(/[.,:]+$/g, '')
    if (rawPath) {
      paths.push(rawPath)
    }
  }
  return paths
}

function cappycloudHasParameterDirectory(worktree: string): boolean {
  const cached = CAPPYCLOUD_PARAMETER_DIR_CACHE.get(worktree)
  if (cached !== undefined) {
    return cached
  }

  const stack = [worktree]
  let visited = 0
  while (stack.length > 0 && visited < 5000) {
    const current = stack.pop()!
    visited += 1
    let entries: fs.Dirent[]
    try {
      entries = fs.readdirSync(current, { withFileTypes: true })
    } catch {
      continue
    }
    for (const entry of entries) {
      if (!entry.isDirectory()) {
        continue
      }
      const name = entry.name.toLowerCase()
      if (name === 'parametros') {
        CAPPYCLOUD_PARAMETER_DIR_CACHE.set(worktree, true)
        return true
      }
      if (['.git', 'node_modules', 'bin', 'obj', '.venv', 'venv'].includes(name)) {
        continue
      }
      stack.push(path.join(current, entry.name))
    }
  }

  CAPPYCLOUD_PARAMETER_DIR_CACHE.set(worktree, false)
  return false
}

function cappycloudIsNumericGrepPattern(pattern: unknown): boolean {
  if (typeof pattern !== 'string') {
    return false
  }
  const cleaned = pattern.trim().replace(/\\b/g, '')
  return /^\d{1,12}$/.test(cleaned)
}

function cappycloudValidateNumericParameterGrep(
  toolName: string,
  input: unknown,
  worktree: string,
  numericParameterMode: boolean,
): string | null {
  if (!numericParameterMode || toolName !== 'Grep' || !input || typeof input !== 'object') {
    return null
  }
  const record = input as Record<string, unknown>
  if (!cappycloudIsNumericGrepPattern(record.pattern)) {
    return null
  }
  const rawPath = typeof record.path === 'string' ? record.path : '.'
  const resolvedPath = cappycloudResolveToolPath(worktree, rawPath)
  if (!resolvedPath || path.relative(worktree, resolvedPath) !== '') {
    return null
  }
  const glob = typeof record.glob === 'string' ? record.glob.toLowerCase() : ''
  if (glob.includes('parametros') || !cappycloudHasParameterDirectory(worktree)) {
    return null
  }
  return `Tool blocked: numeric parameter lookup must search inside discovered Parametros directories, not the worktree root. Allowed worktree: ${worktree}. Use find/git ls-files to locate */Parametros, then set Grep path to that directory.`
}

function cappycloudWrapNumericParameterGrepTool(tool: any, worktree: string, numericParameterMode: boolean): any {
  if (!numericParameterMode || tool?.name !== 'Grep') {
    return tool
  }
  return {
    ...tool,
    async call(args: any, context: any, canUseTool: any, parentMessage: any, onProgress?: any) {
      const guardMessage = cappycloudValidateNumericParameterGrep(tool.name, args, worktree, numericParameterMode)
      if (guardMessage) {
        const mode = args?.output_mode === 'files_with_matches' || args?.output_mode === 'count'
          ? args.output_mode
          : 'content'
        return {
          data: {
            mode,
            numFiles: 0,
            filenames: [],
            content: guardMessage,
            numLines: 0,
            numMatches: 0,
          },
        }
      }
      return tool.call(args, context, canUseTool, parentMessage, onProgress)
    },
  }
}

function cappycloudValidateToolScope(toolName: string, input: unknown, worktree: string): string | null {
  if (CAPPYCLOUD_PATH_GUARDED_TOOLS.has(toolName)) {
    for (const rawPath of cappycloudCollectPathInputs(input)) {
      const resolvedPath = cappycloudResolveToolPath(worktree, rawPath)
      if (resolvedPath && !cappycloudIsInsideWorktree(worktree, resolvedPath)) {
        return `Tool blocked: path outside the conversation worktree. Allowed worktree: ${worktree}. Requested path: ${resolvedPath}.`
      }
    }
  }

  if (CAPPYCLOUD_COMMAND_GUARDED_TOOLS.has(toolName) && input && typeof input === 'object') {
    const command = (input as Record<string, unknown>).command
    if (typeof command === 'string') {
      if (/(^|[\s;&|])cd\s+\.\.(?:\/|\s|$)/.test(command) || /(^|[\s"'=])\.\.(?:\/|$)/.test(command)) {
        return `Tool blocked: command tries to leave the conversation worktree. Allowed worktree: ${worktree}.`
      }
      for (const rawPath of cappycloudExtractRepoPaths(command)) {
        const resolvedPath = cappycloudResolveToolPath(worktree, rawPath)
        if (resolvedPath && !cappycloudIsInsideWorktree(worktree, resolvedPath)) {
          return `Tool blocked: command references a repo path outside the conversation worktree. Allowed worktree: ${worktree}. Requested path: ${resolvedPath}.`
        }
      }
    }
  }

  return null
}

function cappycloudByteLength(value: unknown): number {
  if (value === undefined || value === null) {
    return 0
  }
  if (Buffer.isBuffer(value)) {
    return value.length
  }
  if (value instanceof Uint8Array) {
    return value.byteLength
  }
  if (typeof value === 'string') {
    return Buffer.byteLength(value, 'utf8')
  }
  try {
    return Buffer.byteLength(JSON.stringify(value), 'utf8')
  } catch {
    return 0
  }
}

function cappycloudToolSchemaSize(tool: any): number {
  return cappycloudByteLength({
    name: tool?.name,
    description: tool?.description,
    input_schema: tool?.inputSchema ?? tool?.input_schema ?? tool?.schema,
  })
}

function cappycloudAddDiagnosticCategory(
  categories: CappycloudDiagnosticCategory[],
  key: string,
  sizeBytes: number,
) {
  const safeKey = CAPPYCLOUD_DIAGNOSTIC_LABELS.has(key) ? key : 'other'
  const size = Math.max(0, Math.round(sizeBytes))
  if (size <= 0) {
    return
  }
  const existing = categories.find(category => category.key === safeKey)
  if (existing) {
    existing.size_bytes += size
    return
  }
  categories.push({
    key: safeKey,
    label: CAPPYCLOUD_DIAGNOSTIC_LABELS.get(safeKey) ?? 'Outros',
    size_bytes: size,
  })
}

function cappycloudPayloadDiagnostic(
  req: any,
  previousMessages: any[],
  tools: any[],
  commands: any[],
) {
  const categories: CappycloudDiagnosticCategory[] = []
  cappycloudAddDiagnosticCategory(categories, 'user_message', cappycloudByteLength(req.message))
  cappycloudAddDiagnosticCategory(categories, 'conversation_history', cappycloudByteLength(previousMessages))
  cappycloudAddDiagnosticCategory(
    categories,
    'attachments',
    Array.isArray(req.attachments)
      ? req.attachments.reduce((sum: number, attachment: any) => {
          return sum + cappycloudByteLength(attachment?.data) + cappycloudByteLength(attachment?.mime_type)
        }, 0)
      : 0,
  )
  const builtinToolBytes = tools
    .filter(tool => !tool?.isMcp)
    .reduce((sum, tool) => sum + cappycloudToolSchemaSize(tool), 0)
  const mcpToolBytes = tools
    .filter(tool => tool?.isMcp)
    .reduce((sum, tool) => sum + cappycloudToolSchemaSize(tool), 0)
  cappycloudAddDiagnosticCategory(categories, 'tool_schemas', builtinToolBytes)
  cappycloudAddDiagnosticCategory(categories, 'mcp_tool_schemas', mcpToolBytes + cappycloudByteLength(commands.map(command => command?.name ?? command)))
  cappycloudAddDiagnosticCategory(
    categories,
    'runtime_context',
    cappycloudByteLength({
      model: req.model,
      provider_base_url: req.provider_base_url ? 'configured' : '',
      provider_api_format: req.provider_api_format,
      session_id: req.session_id,
    }),
  )

  categories.sort((a, b) => b.size_bytes - a.size_bytes)
  const totalSizeBytes = categories.reduce((sum, category) => sum + category.size_bytes, 0)
  for (const category of categories) {
    category.percentage = totalSizeBytes > 0 ? Math.round((category.size_bytes / totalSizeBytes) * 1000) / 10 : 0
  }
  return {
    total_size_bytes: totalSizeBytes,
    source: 'openclaude',
    generated_at: new Date().toISOString(),
    categories,
  }
}
