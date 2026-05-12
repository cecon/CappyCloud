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

export type RepoSelection = {
  slug: string
  alias?: string | null
  base_branch?: string | null
}

export type Conversation = {
  id: string
  title: string
  created_at: string
  updated_at: string
  repos: RepoSelection[]
  session_root: string | null
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

export interface StatusEvent {
  message: string
  stage?: 'session' | 'repository' | 'ready' | 'agent'
  mode?: 'initializing' | 'resuming'
}

export interface StreamHandlers {
  onText(accumulated: string): void
  onToolStart(tool: ToolStartEvent): void
  onToolResult(tool: ToolResultEvent): void
  onActionRequired(action: ActionRequiredEvent): void
  onStatus(status: StatusEvent): void
  onError(message: string): void
  /** Acumulador final de tokens/modelo enviado quando o agente termina o turno. */
  onDone?(usage: DoneEvent): void
  signal?: AbortSignal
}

export async function fetchConversations(token: string): Promise<Conversation[]> {
  const res = await apiFetch('/api/conversations', {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) throw new Error('Não foi possível carregar conversas')
  return res.json()
}

export async function createConversation(
  token: string,
  repos: RepoSelection[] = [],
): Promise<Conversation> {
  const body: Record<string, unknown> = { repos }
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
): Promise<void> {
  const { signal, ...eventHandlers } = handlers
  const bodyPayload: Record<string, unknown> = { content }
  if (modelId) bodyPayload.model_id = modelId
  if (attachmentIds && attachmentIds.length > 0) bodyPayload.attachment_ids = attachmentIds
  const res = await apiFetch(`/api/conversations/${conversationId}/messages/stream`, {
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
            })
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
            })
            break
        }
      } catch {
        // Ignore malformed SSE lines
      }
    }
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
  kind: 'image'
  has_description: boolean
  vision_model_used: string | null
  uploaded_at: string
  preview_url: string
}

/**
 * Faz upload de uma imagem para uma conversa. O backend gera descrição
 * textual via modelo de visão (síncrono, ~3-8s); a Promise resolve só após
 * isso para o front conseguir mostrar o status `vision_model_used`.
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
  slug: string
  name: string
  url: string
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
    `/api/conversations/${conversationId}/file?path=${encodeURIComponent(path)}`,
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
    `/api/git-providers/${providerId}/token?token=${encodeURIComponent(newToken)}`,
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
  provider_id: string | null
  sandbox_id: string | null
  sandbox_status: string
  active: boolean
  created_at: string
}

export interface RepositoryCreate {
  slug: string
  name: string
  clone_url: string
  default_branch: string
  provider_id?: string | null
  sandbox_id?: string | null
  /** PAT inline: se preenchido, o backend cria/atualiza um GitProvider implícito. */
  pat_token?: string | null
  /** Tipo do provider (azure_devops, github…). Inferido da URL se omitido. */
  provider_type?: string | null
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

export interface Sandbox {
  id: string
  name: string
  host: string
  grpc_port: number
  session_port: number
  status: string
  created_at: string
}

export async function fetchSandboxes(token: string): Promise<Sandbox[]> {
  const res = await apiFetch('/api/sandboxes', {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) return []
  return res.json()
}

// ── AI Models ────────────────────────────────────────────────────────────────

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
  title: string
  slug?: string
  summary?: string
  content: string
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

export type DocumentSourceType = 'pdf' | 'xlsx' | 'url' | 'text'

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
  created_at: string
  updated_at: string
  indexed_at: string | null
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

export async function deleteRepoDocument(token: string, docId: string): Promise<void> {
  const res = await apiFetch(`/api/documents/${docId}`, {
    method: 'DELETE',
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) throw new Error('Falha ao remover documento')
}
