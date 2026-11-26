import { useMemo } from 'react'
import { useCurrentUser } from './useCurrentUser'

export type WorkspaceEditScope = {
  /** Sem criar, sincronizar ou remover; edita só CLAUDE.md, prompt modelo e opções. */
  limited: boolean
  /** Workspaces que a pessoa pode editar; `null` = todos (super admin). */
  editableIds: ReadonlySet<string> | null
  /** ADMIN global (super ou não) lê o catálogo de sandboxes e repositórios. */
  readsCatalog: boolean
}

/**
 * Quem edita qual workspace na tela de admin. Só o super admin gere todos. Os
 * demais (admin de workspace ou ADMIN global comum) editam, em modo limitado,
 * os workspaces de que são admin, como a API faz em ``get_workspace_manager_scope``.
 */
export function useWorkspaceEditScope(): WorkspaceEditScope {
  const state = useCurrentUser()
  const user = state.status === 'ready' ? state.user : null
  const globalAdmin = !!user && user.role === 'admin'
  const superAdmin = globalAdmin && !!user?.is_super_admin
  const key = user && !superAdmin ? (user.admin_workspace_ids ?? []).join(',') : ''
  return useMemo(
    () =>
      superAdmin
        ? { limited: false, editableIds: null, readsCatalog: true }
        : { limited: true, editableIds: new Set(key ? key.split(',') : []), readsCatalog: globalAdmin },
    [superAdmin, globalAdmin, key],
  )
}
