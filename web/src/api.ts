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
  agent_id?: string | null
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
  const res = await apiFetch('/api/conversations', {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) throw new Error('Não foi possível carregar conversas')
  return res.json()
}

export async function createConversation(
  token: string,
  repos: RepoSelection[] = [],
  agentId: string | null = null,
): Promise<Conversation> {
  const body: Record<string, unknown> = { repos }
  if (agentId) body.agent_id = agentId
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
  handlers: StreamHandlers
): Promise<void> {
  const { signal, ...eventHandlers } = handlers
  const res = await apiFetch(`/api/conversations/${conversationId}/messages/stream`, {
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
  if (!res.ok) throw new Error('Erro ao carregar diff')
  return res.json()
}

export async function fetchConversationFiles(
  token: string,
  conversationId: string
): Promise<{ worktree_path: string; files: string[] }> {
  const res = await apiFetch(`/api/conversations/${conversationId}/files`, {
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
  const res = await apiFetch(
    `/api/conversations/${conversationId}/file?path=${encodeURIComponent(path)}`,
    { headers: { Authorization: `Bearer ${token}` } }
  )
  if (!res.ok) throw new Error('Erro ao ler ficheiro')
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

// ── Agents & Skills ──────────────────────────────────────────────────────────

export interface Agent {
  id: string
  slug: string
  name: string
  description: string
  icon: string
  system_prompt: string
  default_model: string | null
  active: boolean
  skills_count: number
  created_at: string
  updated_at: string
}

export interface AgentCreate {
  slug: string
  name: string
  description?: string
  icon?: string
  system_prompt?: string
  default_model?: string | null
  active?: boolean
}

export interface AgentUpdate {
  name?: string
  description?: string
  icon?: string
  system_prompt?: string
  default_model?: string | null
  active?: boolean
}

export async function fetchAgents(token: string): Promise<Agent[]> {
  const res = await apiFetch('/api/agents', {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) return []
  return res.json()
}

export async function fetchAgent(token: string, id: string): Promise<Agent> {
  const res = await apiFetch(`/api/agents/${id}`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) throw new Error('Agente não encontrado')
  return res.json()
}

export async function createAgent(token: string, data: AgentCreate): Promise<Agent> {
  const res = await apiFetch('/api/agents', {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || 'Falha ao criar agente')
  }
  return res.json()
}

export async function updateAgent(
  token: string,
  id: string,
  data: AgentUpdate,
): Promise<Agent> {
  const res = await apiFetch(`/api/agents/${id}`, {
    method: 'PATCH',
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || 'Falha ao atualizar agente')
  }
  return res.json()
}

export async function deleteAgent(token: string, id: string): Promise<void> {
  const res = await apiFetch(`/api/agents/${id}`, {
    method: 'DELETE',
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) throw new Error('Falha ao remover agente')
}

export interface Skill {
  id: string
  agent_id: string | null
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
  agent_id?: string | null
  title: string
  slug?: string
  summary?: string
  content: string
  tags?: string[]
  source_url?: string | null
}

export async function fetchSkills(
  token: string,
  agentId?: string | null,
): Promise<Skill[]> {
  const url = agentId
    ? `/api/skills?agent_id=${encodeURIComponent(agentId)}`
    : '/api/skills'
  const res = await apiFetch(url, {
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
  agentId: string | null = null,
  tags: string[] = [],
): Promise<Skill> {
  const body: Record<string, unknown> = { url, tags }
  if (agentId) body.agent_id = agentId
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
