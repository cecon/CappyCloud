/**
 * Cliente HTTP para a API CappyCloud (paths relativos `/api` com proxy Vite).
 */

const TOKEN_KEY = 'cappycloud_token'

/**
 * Extrai texto legível do corpo JSON de erro da FastAPI (422, etc.).
 * Evita `[object Object]` quando `msg` é objeto ou a lista contém strings misturadas.
 */
function formatApiErrorPayload(data: unknown): string {
  if (typeof data !== 'object' || data === null) {
    return 'Pedido inválido'
  }
  if (!('detail' in data)) {
    return JSON.stringify(data)
  }
  const detail = (data as { detail: unknown }).detail

  if (typeof detail === 'string') {
    return detail
  }

  if (Array.isArray(detail)) {
    const parts: string[] = []
    for (const item of detail) {
      if (typeof item === 'string') {
        parts.push(item)
        continue
      }
      if (typeof item === 'object' && item !== null) {
        const o = item as Record<string, unknown>
        const loc = o.loc
        const locStr =
          Array.isArray(loc) && loc.length > 0
            ? ` (${loc.filter((x) => x !== 'body').join('.')})`
            : ''
        const msg = o.msg
        if (typeof msg === 'string') {
          parts.push(msg + locStr)
          continue
        }
        if (msg != null && typeof msg === 'object') {
          parts.push(JSON.stringify(msg) + locStr)
          continue
        }
        if (msg != null) {
          parts.push(String(msg) + locStr)
          continue
        }
        parts.push(JSON.stringify(item))
        continue
      }
      parts.push(String(item))
    }
    const out = parts.filter(Boolean).join(' · ')
    return out || 'Pedido inválido'
  }

  if (typeof detail === 'object' && detail !== null) {
    return JSON.stringify(detail)
  }

  return String(detail ?? 'Pedido inválido')
}

/**
 * Mensagem segura para mostrar ao utilizador a partir de qualquer valor em `catch`.
 */
export function errorToUserMessage(e: unknown): string {
  if (e instanceof Error) {
    return e.message || 'Erro desconhecido'
  }
  if (typeof e === 'string') {
    return e
  }
  try {
    return JSON.stringify(e)
  } catch {
    return String(e)
  }
}

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string | null): void {
  if (token) localStorage.setItem(TOKEN_KEY, token)
  else localStorage.removeItem(TOKEN_KEY)
}

export async function loginRequest(email: string, password: string): Promise<string> {
  const body = new URLSearchParams()
  body.set('username', email)
  body.set('password', password)
  const res = await fetch('/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: body.toString(),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    const text = formatApiErrorPayload(err) || 'Falha no login'
    throw new Error(String(text))
  }
  const data = (await res.json()) as { access_token: string }
  return data.access_token
}

export async function registerRequest(email: string, password: string): Promise<void> {
  const payload = {
    email: String(email ?? '')
      .trim()
      .toLowerCase(),
    password: String(password ?? ''),
  }
  const res = await fetch('/api/auth/register', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json; charset=utf-8' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    const text = formatApiErrorPayload(err) || 'Registo falhou'
    throw new Error(String(text))
  }
}

export type Conversation = {
  id: string
  title: string
  created_at: string
  updated_at: string
  environment_id: string | null
  env_slug: string | null
  base_branch: string | null
}

export type ChatMessage = {
  id: string
  role: string
  content: string
  created_at: string
}

export interface ToolStartEvent {
  name: string
  input: string
  id: string
}

export interface ToolResultEvent {
  name: string
  output: string
  is_error: boolean
  id: string
}

export interface ActionRequiredEvent {
  prompt_id: string
  question: string
  action_type: number // 0 = confirm (sim/não), 1 = request_info (choices ou free-text)
  choices: string[] | null
}

export interface StreamHandlers {
  onText(accumulated: string): void
  onToolStart(tool: ToolStartEvent): void
  onToolResult(tool: ToolResultEvent): void
  onActionRequired(action: ActionRequiredEvent): void
  onError(message: string): void
  signal?: AbortSignal
}

export async function fetchConversations(token: string): Promise<Conversation[]> {
  const res = await fetch('/api/conversations', {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) throw new Error('Não foi possível carregar conversas')
  return res.json()
}

export async function createConversation(
  token: string,
  environmentId?: string | null,
  baseBranch?: string | null
): Promise<Conversation> {
  const res = await fetch('/api/conversations', {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      environment_id: environmentId ?? null,
      base_branch: baseBranch ?? null,
    }),
  })
  if (!res.ok) throw new Error('Não foi possível criar conversa')
  return res.json()
}

export async function fetchMessages(token: string, conversationId: string): Promise<ChatMessage[]> {
  const res = await fetch(`/api/conversations/${conversationId}/messages`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) throw new Error('Não foi possível carregar mensagens')
  return res.json()
}

/**
 * Envia mensagem e processa o stream SSE JSON com handlers tipados.
 * O backend envia eventos no formato: data: {"type":"...","..."}\n\n
 */
export async function streamAssistantReply(
  token: string,
  conversationId: string,
  content: string,
  handlers: StreamHandlers
): Promise<void> {
  const { signal, ...eventHandlers } = handlers
  const res = await fetch(`/api/conversations/${conversationId}/messages/stream`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ content }),
    signal,
  })
  if (!res.ok) {
    const err = await res.text()
    throw new Error(err || 'Erro no agente')
  }
  const reader = res.body!.getReader()
  const dec = new TextDecoder()
  let buf = ''
  let accText = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buf += dec.decode(value, { stream: true })

    // Process all complete SSE lines; keep any partial line in buf
    const lines = buf.split('\n')
    buf = lines.pop() ?? ''

    for (const line of lines) {
      if (!line.startsWith('data: ')) continue
      try {
        const evt = JSON.parse(line.slice(6)) as Record<string, unknown>
        switch (evt.type) {
          case 'text':
            accText += (evt.content as string) ?? ''
            eventHandlers.onText(accText)
            break
          case 'tool_start':
            eventHandlers.onToolStart({
              name: evt.name as string,
              input: (evt.input as string) ?? '',
              id: evt.id as string,
            })
            break
          case 'tool_result':
            eventHandlers.onToolResult({
              name: evt.name as string,
              output: (evt.output as string) ?? '',
              is_error: (evt.is_error as boolean) ?? false,
              id: evt.id as string,
            })
            break
          case 'action_required':
            eventHandlers.onActionRequired({
              prompt_id: evt.prompt_id as string,
              question: evt.question as string,
              action_type: (evt.action_type as number) ?? 0,
              choices: (evt.choices as string[] | null) ?? null,
            })
            break
          case 'error':
            eventHandlers.onError((evt.message as string) ?? 'Erro desconhecido')
            break
        }
      } catch {
        // Ignore malformed SSE lines
      }
    }
  }
}

// ── Environment lifecycle ─────────────────────────────────────────────────────

export type EnvStatus = 'none' | 'stopped' | 'starting' | 'running'

export interface EnvironmentStatusResponse {
  status: EnvStatus
  container_id: string | null
}

export type RepoEnv = {
  id: string
  slug: string
  name: string
  repo_url: string
  branch: string
  created_at: string
}

export type RepoEnvCreate = {
  slug: string
  name: string
  repo_url: string
  branch?: string
}

/**
 * Lista todos os ambientes de repositório globais.
 */
export async function fetchRepoEnvironments(token: string): Promise<RepoEnv[]> {
  const res = await fetch('/api/environments', {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) throw new Error('Não foi possível carregar ambientes')
  return res.json()
}

/**
 * Cria um novo ambiente de repositório global.
 */
export async function createRepoEnvironment(
  token: string,
  data: RepoEnvCreate
): Promise<RepoEnv> {
  const res = await fetch('/api/environments', {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ branch: 'main', ...data }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || 'Falha ao criar ambiente')
  }
  return res.json()
}

/**
 * Remove um ambiente de repositório global.
 */
export async function deleteRepoEnvironment(token: string, envId: string): Promise<void> {
  const res = await fetch(`/api/environments/${envId}`, {
    method: 'DELETE',
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) throw new Error('Falha ao remover ambiente')
}

/**
 * Returns the current status of a repo environment's Docker container.
 */
export async function getRepoEnvironmentStatus(
  token: string,
  envId: string
): Promise<EnvironmentStatusResponse> {
  try {
    const res = await fetch(`/api/environments/${envId}/status`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    if (!res.ok) return { status: 'none', container_id: null }
    return res.json()
  } catch {
    return { status: 'none', container_id: null }
  }
}

/**
 * Triggers environment creation or restart in the background (fire-and-forget).
 */
export async function wakeRepoEnvironment(token: string, envId: string): Promise<void> {
  try {
    await fetch(`/api/environments/${envId}/wake`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
    })
  } catch {
    // Ignore network errors — the pipeline will create the env on first message anyway
  }
}

/**
 * Returns the current status of the user's sandbox environment.
 * @deprecated Use getRepoEnvironmentStatus with a specific envId instead.
 */
export async function getEnvironmentStatus(_token: string): Promise<EnvironmentStatusResponse> {
  return { status: 'none', container_id: null }
}

/**
 * Triggers environment creation or restart in the background (fire-and-forget).
 * @deprecated Use wakeRepoEnvironment with a specific envId instead.
 */
export async function wakeEnvironment(_token: string): Promise<void> {
  // no-op — environments are now per-slug, not per-user
}

// ── Conversation cancel ───────────────────────────────────────────────────────

export async function cancelConversation(token: string, conversationId: string): Promise<boolean> {
  try {
    const res = await fetch(`/api/conversations/${conversationId}/cancel`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
    })
    if (!res.ok) return false
    const data = (await res.json()) as { cancelled: boolean }
    return data.cancelled ?? false
  } catch {
    return false
  }
}

// ── Diff ──────────────────────────────────────────────────────────────────────

export interface DiffLine {
  type: 'add' | 'remove' | 'context'
  content: string
}

export interface DiffHunk {
  old_start: number
  new_start: number
  lines: DiffLine[]
}

export interface DiffFile {
  path: string
  added: number
  removed: number
  hunks: DiffHunk[]
}

export interface ConversationDiff {
  base_branch: string
  stats: { added: number; removed: number }
  files: DiffFile[]
}

export async function fetchConversationDiff(
  token: string,
  conversationId: string
): Promise<ConversationDiff> {
  const res = await fetch(`/api/conversations/${conversationId}/diff`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) throw new Error('Erro ao carregar diff')
  return res.json()
}

// ── File explorer ─────────────────────────────────────────────────────────────

export async function fetchConversationFiles(
  token: string,
  conversationId: string
): Promise<{ worktree_path: string; files: string[] }> {
  const res = await fetch(`/api/conversations/${conversationId}/files`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) throw new Error('Erro ao listar ficheiros')
  return res.json()
}

export async function fetchConversationFile(
  token: string,
  conversationId: string,
  path: string
): Promise<{ path: string; content: string }> {
  const res = await fetch(
    `/api/conversations/${conversationId}/file?path=${encodeURIComponent(path)}`,
    { headers: { Authorization: `Bearer ${token}` } }
  )
  if (!res.ok) throw new Error('Erro ao ler ficheiro')
  return res.json()
}
