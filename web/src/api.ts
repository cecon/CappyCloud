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
    return typeof data === 'string' ? data.trim() : 'Pedido inválido'
  }
  if (!('detail' in data)) {
    return stringifyNonEmpty(data)
  }
  const detail = (data as { detail: unknown }).detail

  if (typeof detail === 'string') {
    return detail.trim()
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
    return stringifyNonEmpty(detail)
  }

  return String(detail ?? '').trim()
}

/**
 * Mensagem segura para mostrar ao utilizador a partir de qualquer valor em `catch`.
 */
export function errorToUserMessage(e: unknown): string {
  if (e instanceof Error) {
    return e.message.trim() || 'Erro desconhecido'
  }
  if (typeof e === 'string') {
    return e.trim() || 'Erro desconhecido'
  }
  try {
    return stringifyNonEmpty(e) || 'Falha inesperada. Tente novamente ou consulte os logs da API.'
  } catch {
    return String(e).trim() || 'Falha inesperada. Tente novamente ou consulte os logs da API.'
  }
}

function stringifyNonEmpty(value: unknown): string {
  try {
    const text = JSON.stringify(value)
    return text && text !== '{}' && text !== '[]' ? text : ''
  } catch {
    return ''
  }
}

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string | null): void {
  if (token) localStorage.setItem(TOKEN_KEY, token)
  else localStorage.removeItem(TOKEN_KEY)
}

/** Lançado quando a API responde 401. Sinaliza que o token expirou ou é inválido. */
export class AuthError extends Error {
  constructor() {
    super('Sessão expirada. Por favor, faça login novamente.')
    this.name = 'AuthError'
  }
}

/**
 * Wrapper sobre `fetch` que lança `AuthError` em 401
 * e erros genéricos nos outros casos de falha.
 */
async function apiFetch(url: string, init?: RequestInit): Promise<Response> {
  const res = await fetch(url, init)
  if (res.status === 401) throw new AuthError()
  return res
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

export type UserRole = 'admin' | 'user'

export interface CurrentUser {
  id: string
  email: string
  role: UserRole
  is_super_admin: boolean
  must_change_password: boolean
}

/**
 * Cria um novo utilizador. Apenas ADMINs autenticados podem chamar
 * (ADR-005). O parâmetro {@link token} é o JWT do admin solicitante.
 */
export async function registerRequest(
  token: string,
  email: string,
  password: string,
  role: UserRole = 'user',
  mustChangePassword = true,
): Promise<CurrentUser> {
  const payload = {
    email: String(email ?? '')
      .trim()
      .toLowerCase(),
    password: String(password ?? ''),
    role,
    must_change_password: mustChangePassword,
  }
  const res = await apiFetch('/api/auth/register', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json; charset=utf-8',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    const text = formatApiErrorPayload(err) || 'Falha ao criar utilizador'
    throw new Error(String(text))
  }
  return (await res.json()) as CurrentUser
}

/**
 * Devolve o utilizador autenticado (com {@link UserRole}). O frontend usa
 * isto após login para decidir a navegação admin (ADR-005).
 */
export async function fetchCurrentUser(token: string): Promise<CurrentUser> {
  const res = await apiFetch('/api/auth/me', {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) {
    throw new Error('Não foi possível carregar utilizador')
  }
  return (await res.json()) as CurrentUser
}

export async function changePasswordRequest(
  token: string,
  currentPassword: string,
  newPassword: string,
): Promise<CurrentUser> {
  const res = await apiFetch('/api/auth/change-password', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json; charset=utf-8',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({
      current_password: currentPassword,
      new_password: newPassword,
    }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    const text = formatApiErrorPayload(err) || 'Falha ao alterar senha'
    throw new Error(String(text))
  }
  return (await res.json()) as CurrentUser
}

// ── Admin · Users ────────────────────────────────────────────────────────────

export interface AdminUser {
  id: string
  email: string
  role: UserRole
  is_super_admin: boolean
  must_change_password: boolean
}

/** Lista todos os utilizadores (admin only). */
export async function fetchAdminUsers(token: string): Promise<AdminUser[]> {
  const res = await apiFetch('/api/admin/users', {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || 'Falha ao listar utilizadores')
  }
  return (await res.json()) as AdminUser[]
}

/** Altera o papel de um utilizador (admin only). */
export async function updateAdminUserRole(
  token: string,
  userId: string,
  role: UserRole,
): Promise<AdminUser> {
  const res = await apiFetch(`/api/admin/users/${userId}/role`, {
    method: 'PATCH',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ role }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || 'Falha ao alterar papel')
  }
  return (await res.json()) as AdminUser
}

export type RepoSelection = {
  slug: string
  alias?: string | null
  base_branch?: string | null
}

export type PermissionMode =
  | 'request_permissions'
  | 'accept_edits'
  | 'plan'
  | 'auto'
  | 'bypass_permissions'

export const DEFAULT_PERMISSION_MODE: PermissionMode = 'bypass_permissions'

export interface UserPreferences {
  default_permission_mode: PermissionMode
}

function safePermissionMode(value: unknown): PermissionMode {
  return value === 'accept_edits' ||
    value === 'plan' ||
    value === 'auto' ||
    value === 'bypass_permissions' ||
    value === 'request_permissions'
    ? value
    : DEFAULT_PERMISSION_MODE
}

export async function fetchUserPreferences(token: string): Promise<UserPreferences> {
  const res = await apiFetch('/api/user/preferences', {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) throw new Error('Nao foi possivel carregar preferencias')
  const data = (await res.json()) as { default_permission_mode?: unknown }
  return { default_permission_mode: safePermissionMode(data.default_permission_mode) }
}

export async function updateUserPreferences(
  token: string,
  preferences: Partial<UserPreferences>,
): Promise<UserPreferences> {
  const res = await apiFetch('/api/user/preferences', {
    method: 'PATCH',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(preferences),
  })
  if (!res.ok) throw new Error('Nao foi possivel salvar preferencias')
  const data = (await res.json()) as { default_permission_mode?: unknown }
  return { default_permission_mode: safePermissionMode(data.default_permission_mode) }
}

export type Conversation = {
  id: string
  user_id?: string | null
  user_email?: string | null
  title: string
  created_at: string
  updated_at: string
  sandbox_id: string | null
  repos: RepoSelection[]
  session_root: string | null
  permission_mode: PermissionMode
}

export type ChatMessage = {
  id: string
  role: string
  content: string
  created_at: string
  /** Modelo IA usado para gerar a resposta (apenas em mensagens do assistente). */
  model_used?: string | null
  prompt_tokens?: number
  completion_tokens?: number
  cost_usd?: number
  payload_diagnostics?: PayloadSizeBreakdown | null
}

export type PayloadSizeCategory = {
  key: string
  label: string
  size_bytes: number
  percentage?: number | null
}

export type PayloadSizeBreakdown = {
  total_size_bytes: number
  categories: PayloadSizeCategory[]
  source?: string | null
  generated_at?: string | null
}

export interface ConversationUsage {
  total_prompt_tokens: number
  total_completion_tokens: number
  total_cost_usd: number
}

export interface DoneEvent {
  model_used: string | null
  prompt_tokens: number
  completion_tokens: number
  fallback?: {
    selected_model?: string
    final_model?: string
    reason?: string
  } | null
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

export interface CommandStartEvent {
  command: string
  label: string
}

export type CommandResultStatus =
  | 'started'
  | 'waiting_for_input'
  | 'completed'
  | 'unavailable'
  | 'failed'
  | 'cancelled'

export interface CommandResultEvent {
  command: string
  status: CommandResultStatus
  summary: string
  details_markdown?: string | null
}

export interface ActionRequiredEvent {
  prompt_id: string
  question: string
  action_type: number // 0 = confirm (sim/não), 1 = request_info (choices ou free-text)
  choices: string[] | null
}

export interface StatusEvent {
  message: string
  stage?: 'session' | 'repository' | 'ready' | 'agent'
  mode?: 'initializing' | 'resuming'
  state?: 'active' | 'done'
  metadata?: {
    permission_warning?: {
      runtime_confirmed: boolean
      source: 'openclaude_startup_alert'
    }
  }
}

export interface StreamHandlers {
  onText(accumulated: string): void
  onToolStart(tool: ToolStartEvent): void
  onToolResult(tool: ToolResultEvent): void
  onCommandStart? (event: CommandStartEvent): void
  onCommandResult? (event: CommandResultEvent): void
  onActionRequired(action: ActionRequiredEvent): void
  onStatus(status: StatusEvent): void
  onError(message: string): void
  onCursor? (cursor: number): void
  onPayloadDiagnostic? (diagnostics: PayloadSizeBreakdown): void
  /** Acumulador final de tokens/modelo enviado quando o agente termina o turno. */
  onDone? (usage: DoneEvent): void
  signal?: AbortSignal
}

const PAYLOAD_CATEGORY_LABELS: Record<string, string> = {
  user_message: 'Mensagem do usuario',
  conversation_history: 'Historico da conversa',
  repository_context: 'Contexto do repositorio',
  attachments: 'Anexos',
  tool_results: 'Resultados de ferramentas',
  tool_schemas: 'Ferramentas',
  mcp_tool_schemas: 'Ferramentas MCP',
  runtime_context: 'Contexto de runtime',
  other: 'Outros',
}

function parsePayloadDiagnostics(value: unknown): PayloadSizeBreakdown | null {
  if (!value || typeof value !== 'object') return null
  const raw = value as Record<string, unknown>
  const rawCategories = Array.isArray(raw.categories) ? raw.categories : []
  const categoriesByKey = new Map<string, PayloadSizeCategory>()

  for (const item of rawCategories) {
    if (!item || typeof item !== 'object') continue
    const record = item as Record<string, unknown>
    const key = typeof record.key === 'string' && record.key in PAYLOAD_CATEGORY_LABELS
      ? record.key
      : 'other'
    const size = safeByteCount(record.size_bytes)
    if (size <= 0) continue
    const current = categoriesByKey.get(key)
    if (current) {
      current.size_bytes += size
    } else {
      categoriesByKey.set(key, {
        key,
        label: PAYLOAD_CATEGORY_LABELS[key],
        size_bytes: size,
        percentage: 0,
      })
    }
  }

  const categories = [...categoriesByKey.values()].sort((a, b) => b.size_bytes - a.size_bytes)
  const total = categories.length
    ? categories.reduce((sum, category) => sum + category.size_bytes, 0)
    : safeByteCount(raw.total_size_bytes)
  if (total <= 0) return null
  for (const category of categories) {
    category.percentage = Math.round((category.size_bytes / total) * 1000) / 10
  }

  return {
    total_size_bytes: total,
    categories,
    source: safeDiagnosticSource(raw.source),
    generated_at: safeDiagnosticText(raw.generated_at),
  }
}

function safeByteCount(value: unknown): number {
  const numeric = typeof value === 'number' ? value : Number(value)
  return Number.isFinite(numeric) ? Math.max(0, Math.round(numeric)) : 0
}

function safeDiagnosticSource(value: unknown): string {
  const source = typeof value === 'string' ? value.trim().toLowerCase() : 'openclaude'
  return source === 'openclaude' || source === 'cappycloud' || source === 'agent'
    ? source
    : 'openclaude'
}

function safeDiagnosticText(value: unknown): string {
  const text = typeof value === 'string' ? value.trim() : ''
  return /^[A-Za-z0-9_.:+-]{1,64}$/.test(text) ? text : ''
}

function safePermissionWarningMetadata(value: unknown): StatusEvent['metadata'] | undefined {
  if (!value || typeof value !== 'object') return undefined
  const metadata = value as Record<string, unknown>
  const warning = metadata.permission_warning
  if (!warning || typeof warning !== 'object') return undefined
  const warningRecord = warning as Record<string, unknown>
  const runtimeConfirmed = warningRecord.runtime_confirmed === true
  const source = warningRecord.source === 'openclaude_startup_alert'
    ? 'openclaude_startup_alert'
    : null
  if (!runtimeConfirmed || source === null) return undefined
  return {
    permission_warning: {
      runtime_confirmed: true,
      source,
    },
  }
}

function parseFallbackNotice(value: unknown): DoneEvent['fallback'] {
  if (!value || typeof value !== 'object') return null
  const record = value as Record<string, unknown>
  const selectedModel = safeModelText(record.selected_model)
  const finalModel = safeModelText(record.final_model)
  const reason = safeDiagnosticText(record.reason)
  if (!selectedModel || !finalModel || selectedModel === finalModel) return null
  return {
    selected_model: selectedModel,
    final_model: finalModel,
    reason: reason || 'runtime_model_changed',
  }
}

function safeModelText(value: unknown): string {
  const text = typeof value === 'string' ? value.trim() : ''
  return /^[A-Za-z0-9_.:/@+-]{1,256}$/.test(text) ? text : ''
}

export async function fetchConversations(
  token: string,
  options: { scope?: 'own' | 'all' } = {},
): Promise<Conversation[]> {
  const params = new URLSearchParams()
  if (options.scope) params.set('scope', options.scope)
  const suffix = params.toString() ? `?${params.toString()}` : ''
  const res = await apiFetch(`/api/conversations${suffix}`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) throw new Error('Não foi possível carregar conversas')
  return res.json()
}

export async function createConversation(
  token: string,
  repos: RepoSelection[] = [],
  modelId?: string | null,
  sandboxId?: string | null,
): Promise<Conversation> {
  const body: Record<string, unknown> = { repos }
  if (modelId) body.model_id = modelId
  if (sandboxId) body.sandbox_id = sandboxId
  const res = await apiFetch('/api/conversations', {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error('Não foi possível criar conversa')
  return res.json()
}

export async function fetchMessages(token: string, conversationId: string): Promise<ChatMessage[]> {
  const res = await apiFetch(`/api/conversations/${conversationId}/messages`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) throw new Error('Não foi possível carregar mensagens')
  return res.json()
}

export type SlashCommandArgument = {
  name: string
  label: string
  required: boolean
  value_hint: string
  allowed_values: string[]
  sensitive: boolean
}

export type SlashCommandAvailability = {
  state: 'available' | 'needs_arguments' | 'needs_confirmation' | 'blocked' | 'unavailable'
  reason?: string | null
  required_role?: string | null
  required_capability?: string | null
}

export type SlashCommand = {
  name: string
  description: string
  source: 'upstream' | 'cappycloud' | 'runtime' | string
  category: string
  arguments: SlashCommandArgument[]
  availability: SlashCommandAvailability
  requires_confirmation: boolean
  confirmation_reason?: string | null
  execution_mode: 'chat_action' | 'runtime_command' | 'unavailable' | string
}

export type SlashCommandCatalog = {
  runtime_version: string
  runtime_commit: string
  generated_at: string
  commands: SlashCommand[]
}

export type SlashCommandExecutionResponse = {
  status: 'needs_confirmation' | 'accepted' | 'unavailable' | 'failed' | 'completed'
  message?: string | null
  confirmation?: {
    message: string
    confirm_label: string
    cancel_label: string
  } | null
  stream?: {
    conversation_id: string
    client_request_id: string
  } | null
}

export async function listSlashCommands(
  token: string,
  conversationId: string,
): Promise<SlashCommandCatalog> {
  const res = await apiFetch(`/api/conversations/${conversationId}/commands`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) throw new Error('Nao foi possivel carregar comandos')
  return res.json()
}

export async function executeSlashCommand(
  token: string,
  conversationId: string,
  payload: {
    command: string
    arguments?: Record<string, unknown>
    confirmed?: boolean
    client_request_id: string
  },
): Promise<SlashCommandExecutionResponse> {
  const res = await apiFetch(`/api/conversations/${conversationId}/commands/execute`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      command: payload.command,
      arguments: payload.arguments ?? {},
      confirmed: payload.confirmed ?? false,
      client_request_id: payload.client_request_id,
    }),
  })
  if (!res.ok) throw new Error((await res.text()) || 'Nao foi possivel executar comando')
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
  handlers: StreamHandlers,
  modelId?: string | null,
  attachmentIds?: string[] | null,
  permissionMode?: PermissionMode | null,
  cursor?: number | null,
  actionReply = false,
): Promise<void> {
  const { signal, ...eventHandlers } = handlers
  const bodyPayload: Record<string, unknown> = { content }
  if (modelId) bodyPayload.model_id = modelId
  if (attachmentIds && attachmentIds.length > 0) bodyPayload.attachment_ids = attachmentIds
  if (permissionMode) bodyPayload.permission_mode = permissionMode
  if (actionReply) bodyPayload.action_reply = true
  let retryCursor = cursor
  let retries = 0
  let reader: ReadableStreamDefaultReader<Uint8Array>

  async function openReader(): Promise<ReadableStreamDefaultReader<Uint8Array>> {
    const qs = retryCursor != null ? `?cursor=${encodeURIComponent(String(retryCursor))}` : ''
    const res = await apiFetch(`/api/conversations/${conversationId}/messages/stream${qs}`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(bodyPayload),
      signal,
    })
    if (!res.ok) {
      const err = await res.text()
      throw new Error(err || 'Erro no agente')
    }
    return res.body!.getReader()
  }
  reader = await openReader()
  const dec = new TextDecoder()
  let buf = ''
  let accText = ''
  let sawDone = false
  let lastCursor = cursor

  while (!sawDone) {
    let chunk: ReadableStreamReadResult<Uint8Array>
    try {
      chunk = await reader.read()
    } catch (e) {
      if (e instanceof Error && e.name === 'AbortError') throw e
      if (lastCursor == null || retries >= 3) throw e
      retries += 1
      retryCursor = lastCursor
      await new Promise((resolve) => setTimeout(resolve, 400 * retries))
      reader = await openReader()
      continue
    }
    const { done, value } = chunk
    if (done) {
      if (!sawDone && lastCursor != null && retries < 3) {
        retries += 1
        retryCursor = lastCursor
        await new Promise((resolve) => setTimeout(resolve, 400 * retries))
        reader = await openReader()
        continue
      }
      break
    }
    retries = 0
    buf += dec.decode(value, { stream: true })

    // Process all complete SSE lines; keep any partial line in buf
    const lines = buf.split('\n')
    buf = lines.pop() ?? ''

    for (const line of lines) {
      if (!line.startsWith('data: ')) continue
      try {
        const evt = JSON.parse(line.slice(6)) as Record<string, unknown>
        if (typeof evt.cursor === 'number') {
          lastCursor = evt.cursor
          eventHandlers.onCursor?.(evt.cursor)
        }
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
          case 'command_start':
            eventHandlers.onCommandStart?.({
              command: (evt.command as string) ?? '',
              label: (evt.label as string) ?? 'Comando iniciado',
            })
            break
          case 'command_result': {
            const status = evt.status
            eventHandlers.onCommandResult?.({
              command: (evt.command as string) ?? '',
              status:
                status === 'started' ||
                status === 'waiting_for_input' ||
                status === 'completed' ||
                status === 'unavailable' ||
                status === 'failed' ||
                status === 'cancelled'
                  ? status
                  : 'failed',
              summary: (evt.summary as string) ?? 'Comando finalizado.',
              details_markdown: (evt.details_markdown as string | null) ?? null,
            })
            break
          }
          case 'action_required':
            eventHandlers.onActionRequired({
              prompt_id: evt.prompt_id as string,
              question: evt.question as string,
              action_type: (evt.action_type as number) ?? 0,
              choices: (evt.choices as string[] | null) ?? null,
            })
            break
          case 'status': {
            const stage = evt.stage
            const mode = evt.mode
            eventHandlers.onStatus({
              message: (evt.message as string) ?? 'Preparando sessão...',
              stage:
                stage === 'session' || stage === 'repository' || stage === 'ready' || stage === 'agent'
                  ? stage
                  : undefined,
              mode: mode === 'initializing' || mode === 'resuming' ? mode : undefined,
              state: evt.state === 'active' || evt.state === 'done' ? evt.state : undefined,
              metadata: safePermissionWarningMetadata(evt.metadata),
            })
            break
          }
          case 'payload_diagnostic': {
            const diagnostics = parsePayloadDiagnostics(evt.diagnostics)
            if (diagnostics) {
              eventHandlers.onPayloadDiagnostic?.(diagnostics)
            }
            break
          }
          case 'error':
            eventHandlers.onError((evt.message as string) ?? 'Erro desconhecido')
            break
          case 'done':
            eventHandlers.onDone?.({
              model_used: (evt.model_used as string | null) ?? null,
              prompt_tokens: (evt.prompt_tokens as number) ?? 0,
              completion_tokens: (evt.completion_tokens as number) ?? 0,
              fallback: parseFallbackNotice(evt.fallback),
            })
            sawDone = true
            break
        }
      } catch {
        // Ignore malformed SSE lines
      }
    }
  }
  if (sawDone) {
    reader.cancel().catch(() => {
      // Stream already closed.
    })
  }
}

// ── Attachments ──────────────────────────────────────────────────────────────

/**
 * Metadado de um anexo (imagem) carregado numa conversa.
 *
 * O campo {@link previewUrl} é um path relativo (sem host) que deve ser
 * concatenado com o base da API para servir a imagem; obriga `Authorization`
 * para download — use {@link fetchAttachmentBlobUrl} para obter um Object URL
 * pronto para `<img src=…>`.
 */
export interface Attachment {
  id: string
  conversation_id: string
  mime_type: string
  original_filename: string
  size_bytes: number
  kind: 'image' | 'text' | 'markdown' | 'log' | 'pdf' | 'docx' | string
  has_description: boolean
  processing_status: 'uploaded' | 'described' | 'indexed' | 'error' | string
  chunks_count: number
  processing_error: string | null
  vision_model_used: string | null
  uploaded_at: string
  preview_url: string
}

/**
 * Faz upload de imagem ou artefato de conversa. Imagens são descritas por
 * visão; textos/documentos são extraídos e indexados em chunks da conversa.
 */
export async function uploadAttachment(
  token: string,
  conversationId: string,
  file: File,
  signal?: AbortSignal,
): Promise<Attachment> {
  const fd = new FormData()
  fd.append('file', file, file.name)
  const res = await apiFetch(`/api/conversations/${conversationId}/attachments`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
    body: fd,
    signal,
  })
  if (!res.ok) {
    const err = await res.text().catch(() => '')
    throw new Error(err || `Falha no upload (HTTP ${res.status})`)
  }
  return (await res.json()) as Attachment
}

/**
 * Apaga um anexo (storage físico + registo no banco). 204 No Content em sucesso.
 */
export async function deleteAttachment(
  token: string,
  conversationId: string,
  attachmentId: string,
): Promise<void> {
  const res = await apiFetch(
    `/api/conversations/${conversationId}/attachments/${attachmentId}`,
    {
      method: 'DELETE',
      headers: { Authorization: `Bearer ${token}` },
    },
  )
  if (!res.ok && res.status !== 204) {
    throw new Error(`Falha ao remover anexo (HTTP ${res.status})`)
  }
}

/**
 * Faz GET autenticado da imagem e devolve um Object URL pronto para usar em
 * `<img src=…>`. **Lembrar de revogar com `URL.revokeObjectURL` no unmount**
 * para libertar memória.
 */
export async function fetchAttachmentBlobUrl(
  token: string,
  conversationId: string,
  attachmentId: string,
): Promise<string> {
  const res = await apiFetch(
    `/api/conversations/${conversationId}/attachments/${attachmentId}`,
    { headers: { Authorization: `Bearer ${token}` } },
  )
  if (!res.ok) {
    throw new Error(`Falha ao carregar preview (HTTP ${res.status})`)
  }
  const blob = await res.blob()
  return URL.createObjectURL(blob)
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
  const res = await apiFetch('/api/environments', {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) throw new Error('Não foi possível carregar ambientes')
  return res.json()
}

export async function createRepoEnvironment(
  token: string,
  data: RepoEnvCreate
): Promise<RepoEnv> {
  const res = await apiFetch('/api/environments', {
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

export async function deleteRepoEnvironment(token: string, envId: string): Promise<void> {
  const res = await apiFetch(`/api/environments/${envId}`, {
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
    const res = await apiFetch(`/api/conversations/${conversationId}/cancel`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
      keepalive: true,
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

export interface Workspace {
  id: string
  slug: string
  name: string
  url: string
  sandbox_id: string | null
  confluence_url: string
  confluence_space: string
  confluence_labels: string[]
  sandbox_status: string
}

export async function fetchWorkspaces(token: string): Promise<Workspace[]> {
  const res = await apiFetch('/api/workspaces', {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) return []
  return res.json()
}

export async function fetchBranches(
  token: string,
  slug: string,
): Promise<{ branches: string[]; default: string }> {
  const res = await apiFetch(`/api/workspaces/${encodeURIComponent(slug)}/branches`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) return { branches: ['main'], default: 'main' }
  return res.json()
}

export async function fetchConversationDiff(
  token: string,
  conversationId: string
): Promise<ConversationDiff> {
  const res = await apiFetch(`/api/conversations/${conversationId}/diff`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(data) || 'Erro ao carregar diff')
  }
  return res.json()
}

export async function fetchConversationFiles(
  token: string,
  conversationId: string
): Promise<{ worktree_path: string; files: string[] }> {
  const res = await apiFetch(`/api/conversations/${conversationId}/files`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(data) || 'Erro ao listar ficheiros')
  }
  return res.json()
}

export async function fetchConversationFile(
  token: string,
  conversationId: string,
  path: string
): Promise<{ path: string; content: string }> {
  const res = await apiFetch(
    `/api/conversations/${conversationId}/file?? path=${encodeURIComponent(path)}`,
    { headers: { Authorization: `Bearer ${token}` } }
  )
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(data) || 'Erro ao ler ficheiro')
  }
  return res.json()
}

// ── Pull Request ──────────────────────────────────────────────────────────────

export interface CreatePrResult {
  pr_url: string
  pr_number: number
  head_branch: string
}

export async function createConversationPr(
  token: string,
  conversationId: string,
  title?: string
): Promise<CreatePrResult> {
  const res = await apiFetch(`/api/conversations/${conversationId}/create-pr`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ title: title ?? null }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || 'Falha ao criar PR')
  }
  return res.json()
}

// ── Git Providers ────────────────────────────────────────────────────────────

export type GitProviderType = 'github' | 'azure_devops' | 'gitlab' | 'bitbucket'

export interface GitProvider {
  id: string
  name: string
  provider_type: GitProviderType | string
  base_url: string
  org_or_project: string
  active: boolean
  created_at: string
}

export interface GitProviderCreate {
  name: string
  provider_type: GitProviderType | string
  base_url?: string
  org_or_project?: string
  token: string
}

export async function fetchGitProviders(token: string): Promise<GitProvider[]> {
  const res = await apiFetch('/api/git-providers', {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) return []
  return res.json()
}

export async function createGitProvider(
  token: string,
  data: GitProviderCreate,
): Promise<GitProvider> {
  const res = await apiFetch('/api/git-providers', {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || 'Falha ao criar provedor')
  }
  return res.json()
}

export async function updateGitProviderToken(
  token: string,
  providerId: string,
  newToken: string,
): Promise<GitProvider> {
  const res = await apiFetch(
    `/api/git-providers/${providerId}/token?? token=${encodeURIComponent(newToken)}`,
    {
      method: 'PATCH',
      headers: { Authorization: `Bearer ${token}` },
    },
  )
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || 'Falha ao atualizar token')
  }
  return res.json()
}

export async function deleteGitProvider(token: string, providerId: string): Promise<void> {
  const res = await apiFetch(`/api/git-providers/${providerId}`, {
    method: 'DELETE',
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) throw new Error('Falha ao remover provedor')
}

// ── Repositories ────────────────────────────────────────────────────────────

export interface Repository {
  id: string
  slug: string
  name: string
  clone_url: string
  default_branch: string
  confluence_url: string
  confluence_space: string
  confluence_labels: string[]
  provider_id: string | null
  sandbox_id: string | null
  sandbox_status: string
  active: boolean
  created_at: string
  signoz_service_name?: string | null
}

export interface RepositoryCreate {
  slug: string
  name: string
  clone_url: string
  default_branch: string
  confluence_url?: string
  confluence_space?: string
  confluence_labels?: string[]
  provider_id?: string | null
  sandbox_id?: string | null
  /** PAT inline: se preenchido, o backend cria/atualiza um GitProvider implícito. */
  pat_token?: string | null
  /** Tipo do provider (azure_devops, github…). Inferido da URL se omitido. */
  provider_type?: string | null
  /** SigNoz service.name para correlacionar logs/traces (deixe vazio se não usar). */
  signoz_service_name?: string | null
}

export async function fetchRepositories(token: string): Promise<Repository[]> {
  const res = await apiFetch('/api/repositories', {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) return []
  return res.json()
}

export async function createRepository(
  token: string,
  data: RepositoryCreate,
): Promise<Repository> {
  const res = await apiFetch('/api/repositories', {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || 'Falha ao criar repositório')
  }
  return res.json()
}

export async function deleteRepository(token: string, repoId: string): Promise<void> {
  const res = await apiFetch(`/api/repositories/${repoId}`, {
    method: 'DELETE',
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) throw new Error('Falha ao remover repositório')
}

export async function updateRepository(
  token: string,
  repoId: string,
  data: RepositoryCreate,
): Promise<Repository> {
  const res = await apiFetch(`/api/repositories/${repoId}`, {
    method: 'PATCH',
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || 'Falha ao atualizar repositório')
  }
  return res.json()
}

export async function syncRepository(token: string, repoId: string): Promise<void> {
  const res = await apiFetch(`/api/repositories/${repoId}/sync`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) throw new Error('Falha ao enfileirar sync')
}

export async function fetchBranchesFromUrl(
  token: string,
  cloneUrl: string,
): Promise<{ branches: string[]; default: string }> {
  const res = await apiFetch('/api/workspaces/branches-from-url', {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ clone_url: cloneUrl }),
  })
  if (!res.ok) return { branches: ['main'], default: 'main' }
  return res.json()
}

// ── Sandboxes ────────────────────────────────────────────────────────────────

export type SandboxRuntime = 'compose' | 'swarm'

export type ContainerStatus =
  | 'not_created'
  | 'starting'
  | 'running'
  | 'configuring'
  | 'configured'
  | 'stopped'
  | 'error'

export interface Sandbox {
  id: string
  name: string
  host: string
  grpc_port: number
  session_port: number
  status: string
  runtime: SandboxRuntime
  image: string
  claude_md?: string
  env_vars: Record<string, string>
  container_status: ContainerStatus
  active_sessions: number
  created_at: string
}

export async function fetchSandboxes(token: string): Promise<Sandbox[]> {
  const res = await apiFetch('/api/sandboxes', {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) return []
  return res.json()
}

// ── Admin · Sandboxes ────────────────────────────────────────────────────────

export interface SandboxAdminCreate {
  name: string
  runtime: SandboxRuntime
  image: string
  claude_md?: string
  env_vars?: Record<string, string>
  host?: string | null
  grpc_port?: number
  session_port?: number
}

export interface SandboxAdminUpdate {
  image?: string
  claude_md?: string
  env_vars?: Record<string, string>
  host?: string
  grpc_port?: number
  session_port?: number
  status?: string
}

/** Lista todas as sandboxes cadastradas (admin only). */
export async function fetchAdminSandboxes(token: string): Promise<Sandbox[]> {
  const res = await apiFetch('/api/admin/sandboxes', {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || 'Falha ao listar sandboxes')
  }
  return (await res.json()) as Sandbox[]
}

export async function createAdminSandbox(
  token: string,
  data: SandboxAdminCreate,
): Promise<Sandbox> {
  const res = await apiFetch('/api/admin/sandboxes', {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || 'Falha ao criar sandbox')
  }
  return (await res.json()) as Sandbox
}

export async function updateAdminSandbox(
  token: string,
  sandboxId: string,
  data: SandboxAdminUpdate,
): Promise<Sandbox> {
  const res = await apiFetch(`/api/admin/sandboxes/${sandboxId}`, {
    method: 'PATCH',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || 'Falha ao atualizar sandbox')
  }
  return (await res.json()) as Sandbox
}

export async function deleteAdminSandbox(token: string, sandboxId: string): Promise<void> {
  const res = await apiFetch(`/api/admin/sandboxes/${sandboxId}`, {
    method: 'DELETE',
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok && res.status !== 204) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || 'Falha ao remover sandbox')
  }
}

export async function cloneAdminSandbox(
  token: string,
  sandboxId: string,
  newName: string,
): Promise<Sandbox> {
  const res = await apiFetch(`/api/admin/sandboxes/${sandboxId}/clone`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ new_name: newName }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || 'Falha ao clonar sandbox')
  }
  return (await res.json()) as Sandbox
}

export async function bootAdminSandbox(token: string, sandboxId: string): Promise<Sandbox> {
  const res = await apiFetch(`/api/admin/sandboxes/${sandboxId}/boot`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || 'Falha ao iniciar sandbox')
  }
  return (await res.json()) as Sandbox
}

export async function stopAdminSandbox(token: string, sandboxId: string): Promise<Sandbox> {
  const res = await apiFetch(`/api/admin/sandboxes/${sandboxId}/stop`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || 'Falha ao parar sandbox')
  }
  return (await res.json()) as Sandbox
}

// ── AI Models ────────────────────────────────────────────────────────────────

export type ModelTier = 'free' | 'paid' | 'unknown'

export interface AiModel {
  id: string
  provider_id: string
  model_id: string
  display_name: string
  capabilities: string[]
  is_default: Record<string, boolean>
  context_window: number
  /** Preço do prompt em USD por 1 milhão de tokens (null = desconhecido). */
  input_cost_per_1m_usd: number | null
  /** Preço do completion em USD por 1 milhão de tokens (null = desconhecido). */
  output_cost_per_1m_usd: number | null
  tier: ModelTier
  active: boolean
  created_at: string
}

export interface AiModelSyncResult {
  provider_id: string
  fetched: number
  created: number
  updated: number
  deactivated: number
}

export async function fetchAiModels(token: string): Promise<AiModel[]> {
  const res = await apiFetch('/api/ai-models', {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) return []
  return res.json()
}

/**
 * Dispara sync do catálogo OpenRouter → DB (cria/atualiza pricing dos modelos).
 */
export async function syncAiModelsFromOpenrouter(
  token: string,
): Promise<AiModelSyncResult> {
  const res = await apiFetch('/api/ai-models/sync-from-openrouter', {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || 'Falha ao sincronizar modelos')
  }
  return res.json()
}

/**
 * Totais agregados de tokens/custo de uma conversa.
 */
export async function fetchConversationUsage(
  token: string,
  conversationId: string,
): Promise<ConversationUsage> {
  const res = await apiFetch(`/api/conversations/${conversationId}/usage`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) {
    return { total_prompt_tokens: 0, total_completion_tokens: 0, total_cost_usd: 0 }
  }
  return res.json()
}

// ── Agent Tasks / Runs ──────────────────────────────────────────────────────

export interface AgentTask {
  id: string
  env_slug: string
  status: 'pending' | 'running' | 'paused' | 'done' | 'error' | string
  triggered_by: string
  prompt: string
  conversation_id: string | null
  started_at: string | null
  completed_at: string | null
  last_event_at: string | null
  created_at: string
}

export interface AgentTaskEvent {
  id: number
  event_type: string
  data: Record<string, unknown>
  created_at: string
}

/**
 * Lista execuções recentes do agente, com filtros opcionais por status e ambiente.
 */
export async function fetchAgentTasks(
  token: string,
  options: { status?: string; envSlug?: string; limit?: number } = {},
): Promise<AgentTask[]> {
  const params = new URLSearchParams()
  if (options.status) params.set('status', options.status)
  if (options.envSlug) params.set('env_slug', options.envSlug)
  if (options.limit) params.set('limit', String(options.limit))
  const suffix = params.toString() ? `?${params.toString()}` : ''
  const res = await apiFetch(`/api/tasks${suffix}`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) return []
  return res.json()
}

/**
 * Carrega eventos persistidos de uma execução do agente.
 */
export async function fetchAgentTaskEvents(
  token: string,
  taskId: string,
  options: { after?: number; limit?: number } = {},
): Promise<AgentTaskEvent[]> {
  const params = new URLSearchParams()
  if (options.after !== undefined) params.set('after', String(options.after))
  if (options.limit) params.set('limit', String(options.limit))
  const suffix = params.toString() ? `?${params.toString()}` : ''
  const res = await apiFetch(`/api/tasks/${encodeURIComponent(taskId)}/events${suffix}`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) throw new Error('Não foi possível carregar eventos da execução')
  return res.json()
}

// ── Skills ───────────────────────────────────────────────────────────────────

export interface Skill {
  id: string
  repository_id: string | null
  slug: string
  title: string
  summary: string
  content: string
  tags: string[]
  source_url: string | null
  active: boolean
  has_embedding: boolean
  created_at: string
  updated_at: string
}

export interface SkillCreate {
  repository_id: string
  title: string
  slug?: string
  summary?: string
  content?: string | null
  tags?: string[]
  source_url?: string | null
}

export async function fetchSkills(token: string): Promise<Skill[]> {
  const res = await apiFetch('/api/skills', {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) return []
  return res.json()
}

export async function createSkill(token: string, data: SkillCreate): Promise<Skill> {
  const res = await apiFetch('/api/skills', {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || 'Falha ao criar skill')
  }
  return res.json()
}

export async function updateSkill(
  token: string,
  id: string,
  data: Partial<SkillCreate> & { active?: boolean },
): Promise<Skill> {
  const res = await apiFetch(`/api/skills/${id}`, {
    method: 'PATCH',
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || 'Falha ao atualizar skill')
  }
  return res.json()
}

export async function deleteSkill(token: string, id: string): Promise<void> {
  const res = await apiFetch(`/api/skills/${id}`, {
    method: 'DELETE',
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) throw new Error('Falha ao remover skill')
}

export async function importSkillFromUrl(
  token: string,
  url: string,
  tags: string[] = [],
): Promise<Skill> {
  const body: Record<string, unknown> = { url, tags }
  const res = await apiFetch('/api/skills/import-url', {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || 'Falha ao importar URL')
  }
  return res.json()
}

// ── Documents (RAG por repositório) ──────────────────────────────────────────

export type DocumentSourceType = 'pdf' | 'xlsx' | 'url' | 'text' | 'markdown' | 'txt' | 'docx'

export interface RepoDocument {
  id: string
  repository_id: string
  source_type: DocumentSourceType | string
  source_uri: string
  title: string
  version: number
  checksum: string | null
  status: 'pending' | 'processing' | 'indexed' | 'error' | string
  error_message: string | null
  chunks_count: number
  graph_nodes_count: number
  graph_edges_count: number
  created_at: string
  updated_at: string
  indexed_at: string | null
}

export interface DocumentGraphSummary {
  document_id: string
  graph_nodes_count: number
  graph_edges_count: number
  sample_tables: string[]
}

export interface DocumentCreate {
  source_type: DocumentSourceType
  source_uri?: string
  title?: string | null
  /** Conteúdo bruto — obrigatório quando source_type='text'. */
  content?: string | null
}

export async function fetchRepoDocuments(
  token: string,
  repoId: string,
): Promise<RepoDocument[]> {
  const res = await apiFetch(`/api/repositories/${repoId}/documents`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) return []
  return res.json()
}

export async function createRepoDocument(
  token: string,
  repoId: string,
  data: DocumentCreate,
): Promise<RepoDocument> {
  const res = await apiFetch(`/api/repositories/${repoId}/documents`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || 'Falha ao criar documento')
  }
  return res.json()
}

export async function uploadRepoDocument(
  token: string,
  repoId: string,
  file: File,
  title: string | null = null,
): Promise<RepoDocument> {
  const form = new FormData()
  form.append('file', file)
  if (title) form.append('title', title)
  const res = await apiFetch(`/api/repositories/${repoId}/documents/upload`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
    body: form,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || 'Falha ao enviar ficheiro')
  }
  return res.json()
}

export async function reindexRepoDocument(
  token: string,
  docId: string,
): Promise<RepoDocument> {
  const res = await apiFetch(`/api/documents/${docId}/reindex`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || 'Falha ao reindexar')
  }
  return res.json()
}

export async function fetchDocumentGraphSummary(
  token: string,
  docId: string,
): Promise<DocumentGraphSummary> {
  const res = await apiFetch(`/api/documents/${docId}/graph-summary`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || 'Falha ao testar graph do documento')
  }
  return res.json()
}


export async function deleteRepoDocument(token: string, docId: string): Promise<void> {
  const res = await apiFetch(`/api/documents/${docId}`, {
    method: 'DELETE',
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) throw new Error('Falha ao remover documento')
}

// ── User · Repository MCP Servers ───────────────────────────────────────────

export interface UserMcpServer {
  id: string
  user_id: string
  repository_id: string
  name: string
  token_preview: string
  enabled: boolean
  created_at: string
  updated_at: string
  last_used_at: string | null
}

export interface UserMcpServerSecret extends UserMcpServer {
  token: string
}

export interface UserMcpServerPayload {
  name: string
  repository_id: string
  enabled: boolean
}

export async function fetchUserMcpServers(token: string): Promise<UserMcpServer[]> {
  const res = await apiFetch('/api/mcp-servers', {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || 'Falha ao listar MCP servers')
  }
  return res.json()
}

export async function createUserMcpServer(
  token: string,
  data: UserMcpServerPayload,
): Promise<UserMcpServerSecret> {
  const res = await apiFetch('/api/mcp-servers', {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || 'Falha ao criar MCP server')
  }
  return res.json()
}

export async function updateUserMcpServer(
  token: string,
  serverId: string,
  data: UserMcpServerPayload,
): Promise<UserMcpServer> {
  const res = await apiFetch(`/api/mcp-servers/${serverId}`, {
    method: 'PUT',
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || 'Falha ao atualizar MCP server')
  }
  return res.json()
}

export async function rotateUserMcpServerToken(
  token: string,
  serverId: string,
): Promise<UserMcpServerSecret> {
  const res = await apiFetch(`/api/mcp-servers/${serverId}/rotate-token`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || 'Falha ao rotacionar token MCP')
  }
  return res.json()
}

export async function deleteUserMcpServer(token: string, serverId: string): Promise<void> {
  const res = await apiFetch(`/api/mcp-servers/${serverId}`, {
    method: 'DELETE',
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok && res.status !== 204) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || 'Falha ao remover MCP server')
  }
}

// ── Admin · MCP Servers (por sandbox) ────────────────────────────────────────

export type McpServer = {
  id: string
  sandbox_id: string
  name: string
  command: string
  args: string[]
  env: Record<string, string>
  enabled: boolean
  created_at: string
  updated_at: string
}

export type McpServerCreate = {
  name: string
  command: string
  args?: string[]
  env?: Record<string, string>
  enabled?: boolean
}

export type McpServerUpdate = McpServerCreate

export async function fetchSandboxMcps(
  token: string,
  sandboxId: string,
): Promise<McpServer[]> {
  const res = await apiFetch(`/api/admin/sandboxes/${sandboxId}/mcps`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || 'Falha ao listar MCPs')
  }
  return res.json()
}

export async function createSandboxMcp(
  token: string,
  sandboxId: string,
  data: McpServerCreate,
): Promise<McpServer> {
  const res = await apiFetch(`/api/admin/sandboxes/${sandboxId}/mcps`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || 'Falha ao criar MCP')
  }
  return res.json()
}

export async function updateSandboxMcp(
  token: string,
  sandboxId: string,
  mcpId: string,
  data: McpServerUpdate,
): Promise<McpServer> {
  const res = await apiFetch(`/api/admin/sandboxes/${sandboxId}/mcps/${mcpId}`, {
    method: 'PUT',
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || 'Falha ao atualizar MCP')
  }
  return res.json()
}

export async function deleteSandboxMcp(
  token: string,
  sandboxId: string,
  mcpId: string,
): Promise<void> {
  const res = await apiFetch(`/api/admin/sandboxes/${sandboxId}/mcps/${mcpId}`, {
    method: 'DELETE',
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok && res.status !== 204) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || 'Falha ao eliminar MCP')
  }
}

// ── Admin · Global Skills catalog ───────────────────────────────────────────

export interface GlobalSkill {
  id: string
  name: string
  description: string
  content: string
  enabled: boolean
  sandbox_ids: string[]
  created_at: string
  updated_at: string
}

export interface GlobalSkillPayload {
  name: string
  description?: string
  content?: string
  enabled?: boolean
  sandbox_ids: string[]
}

export async function fetchGlobalSkills(token: string): Promise<GlobalSkill[]> {
  const res = await apiFetch('/api/admin/global-skills', {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || 'Falha ao listar skills globais')
  }
  return res.json()
}

export async function createGlobalSkill(
  token: string,
  data: GlobalSkillPayload,
): Promise<GlobalSkill> {
  const res = await apiFetch('/api/admin/global-skills', {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || 'Falha ao criar skill global')
  }
  return res.json()
}

export async function updateGlobalSkill(
  token: string,
  skillId: string,
  data: GlobalSkillPayload,
): Promise<GlobalSkill> {
  const res = await apiFetch(`/api/admin/global-skills/${skillId}`, {
    method: 'PUT',
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || 'Falha ao atualizar skill global')
  }
  return res.json()
}

export async function deleteGlobalSkill(token: string, skillId: string): Promise<void> {
  const res = await apiFetch(`/api/admin/global-skills/${skillId}`, {
    method: 'DELETE',
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok && res.status !== 204) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || 'Falha ao eliminar skill global')
  }
}

// ── Admin · Sandbox Skills (projecao das globais por sandbox) ────────────────

export interface SandboxSkill {
  id: string
  sandbox_id: string
  name: string
  description: string
  content: string
  enabled: boolean
  created_at: string
  updated_at: string
}

export interface SandboxSkillPayload {
  name: string
  description?: string
  content?: string
  enabled?: boolean
}

export async function fetchSandboxSkills(
  token: string,
  sandboxId: string,
): Promise<SandboxSkill[]> {
  const res = await apiFetch(`/api/admin/sandboxes/${sandboxId}/skills`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || 'Falha ao listar skills')
  }
  return res.json()
}

export async function createSandboxSkill(
  token: string,
  sandboxId: string,
  data: SandboxSkillPayload,
): Promise<SandboxSkill> {
  const res = await apiFetch(`/api/admin/sandboxes/${sandboxId}/skills`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || 'Falha ao criar skill')
  }
  return res.json()
}

export async function updateSandboxSkill(
  token: string,
  sandboxId: string,
  skillId: string,
  data: SandboxSkillPayload,
): Promise<SandboxSkill> {
  const res = await apiFetch(`/api/admin/sandboxes/${sandboxId}/skills/${skillId}`, {
    method: 'PUT',
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || 'Falha ao atualizar skill')
  }
  return res.json()
}

export async function deleteSandboxSkill(
  token: string,
  sandboxId: string,
  skillId: string,
): Promise<void> {
  const res = await apiFetch(`/api/admin/sandboxes/${sandboxId}/skills/${skillId}`, {
    method: 'DELETE',
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok && res.status !== 204) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || 'Falha ao eliminar skill')
  }
}

// ── Admin · Sandbox Agents (subagents globais por sandbox) ───────────────────

export interface SandboxAgent {
  id: string
  sandbox_id: string
  name: string
  description: string
  system_prompt: string
  model: string
  tools: string[]
  enabled: boolean
  created_at: string
  updated_at: string
}

export interface SandboxAgentPayload {
  name: string
  description?: string
  system_prompt?: string
  model?: string
  tools?: string[]
  enabled?: boolean
}

export async function fetchSandboxAgents(
  token: string,
  sandboxId: string,
): Promise<SandboxAgent[]> {
  const res = await apiFetch(`/api/admin/sandboxes/${sandboxId}/agents`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || 'Falha ao listar agents')
  }
  return res.json()
}

export async function createSandboxAgent(
  token: string,
  sandboxId: string,
  data: SandboxAgentPayload,
): Promise<SandboxAgent> {
  const res = await apiFetch(`/api/admin/sandboxes/${sandboxId}/agents`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || 'Falha ao criar agent')
  }
  return res.json()
}

export async function updateSandboxAgent(
  token: string,
  sandboxId: string,
  agentId: string,
  data: SandboxAgentPayload,
): Promise<SandboxAgent> {
  const res = await apiFetch(`/api/admin/sandboxes/${sandboxId}/agents/${agentId}`, {
    method: 'PUT',
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || 'Falha ao atualizar agent')
  }
  return res.json()
}

export async function deleteSandboxAgent(
  token: string,
  sandboxId: string,
  agentId: string,
): Promise<void> {
  const res = await apiFetch(`/api/admin/sandboxes/${sandboxId}/agents/${agentId}`, {
    method: 'DELETE',
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok && res.status !== 204) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || 'Falha ao eliminar agent')
  }
}

// ── User Access (ADR-005 §2) ────────────────────────────────────────────────

export type AccessResource = 'sandboxes' | 'repositories' | 'ai-models'

async function fetchUserAccess(
  token: string,
  userId: string,
  resource: AccessResource,
): Promise<string[]> {
  const res = await apiFetch(`/api/admin/users/${userId}/access/${resource}`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) return []
  return res.json()
}

async function grantUserAccess(
  token: string,
  userId: string,
  resource: AccessResource,
  resourceId: string,
): Promise<void> {
  const res = await apiFetch(`/api/admin/users/${userId}/access/${resource}/${resourceId}`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok && res.status !== 204) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || 'Falha ao conceder acesso')
  }
}

async function revokeUserAccess(
  token: string,
  userId: string,
  resource: AccessResource,
  resourceId: string,
): Promise<void> {
  const res = await apiFetch(`/api/admin/users/${userId}/access/${resource}/${resourceId}`, {
    method: 'DELETE',
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok && res.status !== 204) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || 'Falha ao revogar acesso')
  }
}

export const fetchUserSandboxAccess = (token: string, userId: string) =>
  fetchUserAccess(token, userId, 'sandboxes')
export const fetchUserRepositoryAccess = (token: string, userId: string) =>
  fetchUserAccess(token, userId, 'repositories')
export const fetchUserAiModelAccess = (token: string, userId: string) =>
  fetchUserAccess(token, userId, 'ai-models')

export const grantUserSandboxAccess = (token: string, userId: string, sandboxId: string) =>
  grantUserAccess(token, userId, 'sandboxes', sandboxId)
export const grantUserRepositoryAccess = (token: string, userId: string, repoId: string) =>
  grantUserAccess(token, userId, 'repositories', repoId)
export const grantUserAiModelAccess = (token: string, userId: string, modelId: string) =>
  grantUserAccess(token, userId, 'ai-models', modelId)

export const revokeUserSandboxAccess = (token: string, userId: string, sandboxId: string) =>
  revokeUserAccess(token, userId, 'sandboxes', sandboxId)
export const revokeUserRepositoryAccess = (token: string, userId: string, repoId: string) =>
  revokeUserAccess(token, userId, 'repositories', repoId)
export const revokeUserAiModelAccess = (token: string, userId: string, modelId: string) =>
  revokeUserAccess(token, userId, 'ai-models', modelId)

export interface BulkTierResult {
  granted: number
}

export async function bulkGrantAiModelsByTier(
  token: string,
  userId: string,
  tier: ModelTier,
): Promise<BulkTierResult> {
  const res = await apiFetch(`/api/admin/users/${userId}/access/ai-models/bulk-tier`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ tier }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || 'Falha ao liberar modelos em lote')
  }
  return res.json()
}

// ── Admin LLM catalog (ADR-006) ─────────────────────────────────────────────

export interface AdminAiProvider {
  id: string
  name: string
  base_url: string
  api_format: 'chat_completions' | 'responses'
  active: boolean
  last_synced_at: string | null
  models_count: number
}

export interface AdminProviderCreate {
  name: string
  base_url: string
  api_format?: 'chat_completions' | 'responses'
  api_key?: string
  model_id?: string
  display_name?: string
  capabilities?: string[]
  context_window?: number
  active?: boolean
  is_default_text?: boolean
  is_default_embedding?: boolean
}

export interface AdminProviderPatch {
  name?: string
  base_url?: string
  api_format?: 'chat_completions' | 'responses'
  api_key?: string
  active?: boolean
}

export async function fetchAdminProviders(token: string): Promise<AdminAiProvider[]> {
  const res = await apiFetch('/api/admin/providers', {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) return []
  return res.json()
}

export async function createAdminProvider(
  token: string,
  payload: AdminProviderCreate,
): Promise<AdminAiProvider> {
  const res = await apiFetch('/api/admin/providers', {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || 'Falha ao cadastrar provider')
  }
  return res.json()
}

export async function patchAdminProvider(
  token: string,
  providerId: string,
  payload: AdminProviderPatch,
): Promise<AdminAiProvider> {
  const res = await apiFetch(`/api/admin/providers/${providerId}`, {
    method: 'PATCH',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || 'Falha ao atualizar provider')
  }
  return res.json()
}

export async function syncAdminProvider(
  token: string,
  providerId: string,
): Promise<AiModelSyncResult> {
  const res = await apiFetch(`/api/admin/providers/${providerId}/sync`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || 'Falha ao sincronizar provider')
  }
  return res.json()
}

export interface AdminModelsFilter {
  provider_id?: string
  tier?: ModelTier
  only_active?: boolean
  include_inactive_providers?: boolean
}

export async function fetchAdminModels(
  token: string,
  filter: AdminModelsFilter = {},
): Promise<AiModel[]> {
  const params = new URLSearchParams()
  if (filter.provider_id) params.set('provider_id', filter.provider_id)
  if (filter.tier) params.set('tier', filter.tier)
  if (filter.only_active) params.set('only_active', 'true')
  if (filter.include_inactive_providers) params.set('include_inactive_providers', 'true')
  const qs = params.toString()
  const url = qs ? `/api/admin/models?${qs}` : '/api/admin/models'
  const res = await apiFetch(url, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) return []
  return res.json()
}

export interface AdminModelPatch {
  active?: boolean
  tier?: ModelTier
  capabilities?: string[]
  is_default_text?: boolean
  is_default_embedding?: boolean
}

export async function patchAdminModel(
  token: string,
  modelId: string,
  patch: AdminModelPatch,
): Promise<AiModel> {
  const res = await apiFetch(`/api/admin/models/${modelId}`, {
    method: 'PATCH',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(patch),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || 'Falha ao atualizar modelo')
  }
  return res.json()
}
