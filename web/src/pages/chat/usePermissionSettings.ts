import { useCallback } from 'react'
import { updateUserPreferences, type ExecutionProfile, type PermissionMode } from '../../api'
import { normalizeExecutionProfile, normalizePermissionMode } from './permissionOptions'
import { updateChatPrefs } from './preferences'
import type { ChatPageState } from './useChatPageState'

/** Troca de modo de permissão e perfil de execução (bloqueada durante o streaming). */
export function usePermissionSettings(st: ChatPageState, token: string) {
  const {
    activeId, streaming, setPermissionModeState, setUserDefaultPermissionMode,
    setPermissionWarningRuntimeConfirmed, setConversations, setExecutionProfileState,
  } = st
  // Os setters vêm do useState (identidade estável); listados só para o lint.
  const setPermissionMode = useCallback(
    (mode: PermissionMode) => {
      if (streaming) return
      setPermissionModeState(mode)
      setUserDefaultPermissionMode(mode)
      setPermissionWarningRuntimeConfirmed(false)
      updateUserPreferences(token, { default_permission_mode: mode })
        .then((prefs) =>
          setUserDefaultPermissionMode(normalizePermissionMode(prefs.default_permission_mode)),
        )
        .catch(() => {})
      if (!activeId) return
      setConversations((prev) =>
        prev.map((conversation) =>
          conversation.id === activeId
            ? { ...conversation, permission_mode: mode }
            : conversation,
        ),
      )
    },
    [
      activeId, streaming, token,
      setPermissionModeState, setUserDefaultPermissionMode, setPermissionWarningRuntimeConfirmed, setConversations,
    ],
  )

  const setExecutionProfile = useCallback((profile: ExecutionProfile) => {
    if (streaming) return
    const next = normalizeExecutionProfile(profile)
    setExecutionProfileState(next)
    updateChatPrefs((prefs) => ({ ...prefs, executionProfile: next }))
  }, [streaming, setExecutionProfileState])

  return { setPermissionMode, setExecutionProfile }
}
