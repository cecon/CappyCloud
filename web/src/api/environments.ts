import { apiFetch, formatApiErrorPayload } from './http'

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
