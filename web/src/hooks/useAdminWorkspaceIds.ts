import { useMemo } from 'react'
import { isWorkspaceAdmin } from '../api/auth'
import { useCurrentUser } from './useCurrentUser'

/**
 * Workspaces que limitam o admin atual: lista para admin de workspace, `null`
 * para ADMIN global (sem limite) ou enquanto o usuário carrega.
 */
export function useAdminWorkspaceIds(): string[] | null {
  const state = useCurrentUser()
  const user = state.status === 'ready' ? state.user : null
  const key = user && isWorkspaceAdmin(user) ? (user.admin_workspace_ids ?? []).join(',') : ''
  return useMemo(() => (key ? key.split(',') : null), [key])
}
