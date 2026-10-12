import { apiFetch, formatApiErrorPayload } from './http'

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
  const res = await apiFetch(`/api/git-providers/${providerId}/token`, {
    method: 'PATCH',
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ token: newToken }),
  })
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
  /** Motivo da última falha de clone/sync (saída do git, sem credenciais). */
  error_message?: string | null
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
