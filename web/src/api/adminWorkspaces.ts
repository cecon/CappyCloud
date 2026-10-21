import { apiFetch, formatApiErrorPayload } from './http'

// ── Admin · Workspaces (super admin) ─────────────────────────────────────────

export interface WorkspaceRepositoryLink {
  repository_id: string
  alias?: string | null
  /** Vazio = default_branch do repositório. */
  base_branch?: string
  /** Somente leitura: o agente consulta, sem worktree nem PR. */
  read_only?: boolean
}

export interface AdminWorkspace {
  id: string
  slug: string
  name: string
  sandbox_id: string
  claude_md: string
  active: boolean
  plan_mode_enabled: boolean
  require_ticket: boolean
  sync_status: 'pending' | 'synced' | 'error' | string
  sync_error: string | null
  last_sync_at: string | null
  created_at: string
  repositories: Array<{
    repository_id: string
    slug: string
    name: string
    alias: string
    base_branch: string
    default_branch: string
    sandbox_status: string
    read_only: boolean
  }>
}

export interface AdminWorkspaceCreate {
  slug: string
  name: string
  sandbox_id: string
  claude_md?: string
  plan_mode_enabled?: boolean
  require_ticket?: boolean
  repositories?: WorkspaceRepositoryLink[]
}

export interface AdminWorkspaceUpdate {
  name?: string
  claude_md?: string
  active?: boolean
  plan_mode_enabled?: boolean
  require_ticket?: boolean
  repositories?: WorkspaceRepositoryLink[]
}

async function workspaceRequest<T>(
  token: string,
  path: string,
  init: RequestInit = {},
  fallback = 'Falha na operação de workspace',
): Promise<T> {
  const res = await apiFetch(`/api/admin/workspaces${path}`, {
    ...init,
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || fallback)
  }
  return (res.status === 204 ? undefined : await res.json()) as T
}

export function fetchAdminWorkspaces(token: string): Promise<AdminWorkspace[]> {
  return workspaceRequest(token, '', {}, 'Falha ao listar workspaces')
}

export function createAdminWorkspace(token: string, data: AdminWorkspaceCreate): Promise<AdminWorkspace> {
  return workspaceRequest(token, '', { method: 'POST', body: JSON.stringify(data) }, 'Falha ao criar workspace')
}

export function updateAdminWorkspace(
  token: string,
  workspaceId: string,
  data: AdminWorkspaceUpdate,
): Promise<AdminWorkspace> {
  return workspaceRequest(
    token,
    `/${workspaceId}`,
    { method: 'PATCH', body: JSON.stringify(data) },
    'Falha ao atualizar workspace',
  )
}

export function syncAdminWorkspace(token: string, workspaceId: string): Promise<AdminWorkspace> {
  return workspaceRequest(token, `/${workspaceId}/sync`, { method: 'POST' }, 'Falha ao sincronizar workspace')
}

/** CSV das conversas do workspace com o número do chamado (admin). */
export async function downloadWorkspaceTickets(token: string, workspaceId: string, slug: string): Promise<void> {
  const res = await apiFetch(`/api/admin/workspaces/${workspaceId}/tickets.csv`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || 'Falha ao exportar os chamados')
  }
  const url = URL.createObjectURL(await res.blob())
  const link = document.createElement('a')
  link.href = url
  link.download = `chamados-${slug}.csv`
  link.click()
  URL.revokeObjectURL(url)
}

export function deleteAdminWorkspace(token: string, workspaceId: string): Promise<void> {
  return workspaceRequest(token, `/${workspaceId}`, { method: 'DELETE' }, 'Falha ao remover workspace')
}

/** Grafo do graphify de um repositório do workspace (knowledge_handler.js). */
export interface KnowledgeRepoStatus {
  alias: string
  slug: string
  commit?: string
  nodes?: number
  edges?: number
  communities?: number
  duration_ms?: number
  warning?: string
  error?: string
  /** Código igual ao da rodada anterior (contagem repetida). */
  unchanged?: boolean
}

export interface KnowledgeStatus {
  state: 'never_built' | 'running' | 'done' | 'partial' | 'error'
  running?: boolean
  started_at?: string
  finished_at?: string
  duration_ms?: number
  nodes?: number
  edges?: number
  error?: string
  repos?: KnowledgeRepoStatus[]
}

export interface KnowledgeFile {
  path: string
  size: number
  modified_at: string
}

export interface WorkspaceKnowledge {
  status: KnowledgeStatus
  files: KnowledgeFile[]
}

export interface KnowledgeFileContent {
  path: string
  size: number
  truncated: boolean
  content: string
}

export function fetchWorkspaceKnowledge(token: string, workspaceId: string): Promise<WorkspaceKnowledge> {
  return workspaceRequest(token, `/${workspaceId}/knowledge`, {}, 'Falha ao ler o conhecimento do workspace')
}

export function fetchWorkspaceKnowledgeFile(
  token: string,
  workspaceId: string,
  path: string,
): Promise<KnowledgeFileContent> {
  const query = new URLSearchParams({ path }).toString()
  return workspaceRequest(token, `/${workspaceId}/knowledge/file?${query}`, {}, 'Falha ao abrir o arquivo')
}

/** Memória do workspace no agentmemory (memory_handler.js). */
export interface WorkspaceMemory {
  id: string
  type: string
  content: string
  concepts: string[]
  files: string[]
  created_at: string
  updated_at?: string
}

export function fetchWorkspaceMemories(
  token: string,
  workspaceId: string,
): Promise<{ total: number; memories: WorkspaceMemory[] }> {
  return workspaceRequest(token, `/${workspaceId}/knowledge/memories`, {}, 'Falha ao ler as memórias do workspace')
}

/** Selos da lista de workspaces (admin_workspace_knowledge.py /summary). */
export interface WorkspaceKnowledgeSummary {
  graph: {
    available?: false
    state?: KnowledgeStatus['state']
    running?: boolean
    finished_at?: string
    nodes?: number
    error?: string
    /** Commits novos (desde o último fetch) em relação ao grafo; null se não dá para saber. */
    behind?: number | null
    /** Repositórios do workspace que ainda não entraram no grafo. */
    missing?: string[]
  }
  memory: { available: boolean; total: number; last_at: string | null; error: string | null }
}

export function fetchWorkspaceKnowledgeSummary(
  token: string,
  workspaceId: string,
): Promise<WorkspaceKnowledgeSummary> {
  return workspaceRequest(token, `/${workspaceId}/knowledge/summary`, {}, 'Falha ao ler o resumo do conhecimento')
}

export function buildWorkspaceKnowledge(token: string, workspaceId: string): Promise<{ queued: boolean }> {
  return workspaceRequest(
    token,
    `/${workspaceId}/knowledge/build`,
    { method: 'POST' },
    'Falha ao pedir a atualização do grafo',
  )
}
