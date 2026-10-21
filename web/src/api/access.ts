import { apiFetch, formatApiErrorPayload } from './http'
import type { ModelTier } from './models'

// ── User Access (ADR-005 §2) ────────────────────────────────────────────────

export type AccessResource = 'sandboxes' | 'repositories' | 'ai-models' | 'workspaces'

async function fetchUserAccess(
  token: string,
  userId: string,
  resource: AccessResource | 'workspaces/admin-flags',
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

/**
 * Acesso a workspaces: ADMIN global ou admin do workspace (este só vê e muda os
 * que administra).
 */
export const fetchUserWorkspaceAccess = (token: string, userId: string) =>
  fetchUserAccess(token, userId, 'workspaces')
export const grantUserWorkspaceAccess = (token: string, userId: string, workspaceId: string) =>
  grantUserAccess(token, userId, 'workspaces', workspaceId)
export const revokeUserWorkspaceAccess = (token: string, userId: string, workspaceId: string) =>
  revokeUserAccess(token, userId, 'workspaces', workspaceId)

/** Workspaces em que a pessoa é admin (ADMIN global). */
export const fetchUserWorkspaceAdminFlags = (token: string, userId: string) =>
  fetchUserAccess(token, userId, 'workspaces/admin-flags')

/** Liga/desliga o admin do workspace; ligar também libera o acesso (ADMIN global). */
export async function setUserWorkspaceAdmin(
  token: string,
  userId: string,
  workspaceId: string,
  isAdmin: boolean,
): Promise<void> {
  const res = await apiFetch(`/api/admin/users/${userId}/access/workspaces/${workspaceId}/admin`, {
    method: 'PUT',
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ is_admin: isAdmin }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || 'Falha ao mudar o admin do workspace')
  }
}

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
