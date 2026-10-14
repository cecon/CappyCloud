import { apiFetch } from './http'

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

export type ExecutionProfile = 'fast' | 'medium' | 'deep'

export const DEFAULT_EXECUTION_PROFILE: ExecutionProfile = 'medium'

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
