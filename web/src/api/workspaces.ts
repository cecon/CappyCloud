import { apiFetch, formatApiErrorPayload } from './http'

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
  /** Vazio quando os repositórios têm bases diferentes. */
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

export interface ProjectSuggestionCard {
  id: string
  title: string
  prompt: string
  category: string
  source: string
  freshness_state: string
}

export interface ProjectSuggestionsResponse {
  repo_slug: string
  repo_name: string
  state: 'calibrated' | 'initial' | 'fallback' | 'empty' | 'error'
  last_calibrated_at: string | null
  cards: ProjectSuggestionCard[]
  diagnostic: {
    using_initial_context: boolean
    reason: string
  }
}

export interface ProjectSuggestionRun {
  id: string
  repository_id: string
  trigger: string
  status: string
  started_at: string | null
  finished_at: string | null
  eligible_message_count: number
  eligible_user_count: number
  suggestions_created: number
  suggestions_activated: number
  suggestions_suppressed: number
  failure_reason: string | null
}

export interface ProjectSuggestionStatus {
  repository_id: string
  counts: Record<string, number>
  last_run: ProjectSuggestionRun | null
}

export interface ProjectSuggestionPatchResult {
  id: string
  status: string
  suppressed_at: string | null
}

export async function fetchWorkspaces(token: string): Promise<Workspace[]> {
  const res = await apiFetch('/api/workspaces', {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) return []
  return res.json()
}

export async function fetchProjectSuggestions(
  token: string,
  repoSlug: string,
  limit = 4,
): Promise<ProjectSuggestionsResponse> {
  const params = new URLSearchParams({ repo_slug: repoSlug, limit: String(limit) })
  const res = await apiFetch(`/api/project-suggestions?${params.toString()}`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) throw new Error('Nao foi possivel carregar sugestoes do projeto')
  return res.json()
}

export async function fetchProjectSuggestionStatus(
  token: string,
  repositoryId: string,
): Promise<ProjectSuggestionStatus> {
  const res = await apiFetch(`/api/project-suggestions/${encodeURIComponent(repositoryId)}/status`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) throw new Error('Nao foi possivel carregar status das sugestoes')
  return res.json()
}

export async function recalibrateProjectSuggestions(
  token: string,
  repositoryId: string,
  force = false,
): Promise<ProjectSuggestionRun> {
  const res = await apiFetch(`/api/project-suggestions/${encodeURIComponent(repositoryId)}/recalibrate`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ trigger: 'manual', force }),
  })
  if (!res.ok) throw new Error('Nao foi possivel recalibrar sugestoes')
  return res.json()
}

export async function updateProjectSuggestionStatus(
  token: string,
  suggestionId: string,
  status: 'active' | 'suppressed',
  reason?: string,
): Promise<ProjectSuggestionPatchResult> {
  const res = await apiFetch(`/api/project-suggestions/${encodeURIComponent(suggestionId)}`, {
    method: 'PATCH',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ status, reason }),
  })
  if (!res.ok) throw new Error('Nao foi possivel atualizar sugestao')
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

export interface RepoPrResult {
  alias: string
  slug: string
  provider?: 'github' | 'azure_devops'
  pr_url?: string
  pr_number?: number
  head_branch?: string
  error?: string
}

export interface CreatePrResult {
  pr_url: string
  pr_number: number
  head_branch: string
  /** Um item por repositório alterado (workspace: vários PRs). */
  prs?: RepoPrResult[]
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
