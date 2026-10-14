import { useEffect, useMemo } from 'react'
import { fetchAccessibleWorkspaces } from '../../api'
import { CHAT_CONVERSATIONS_COLLAPSED_KEY, CONVERSATION_PAGE_SIZE } from './constants'
import { normalizePermissionMode } from './permissionOptions'
import { defaultWorkspaceId } from './preferences'
import type { ChatPageState } from './useChatPageState'

/**
 * Efeitos de base da tela: relógio do stream, preferência visual, paginação da
 * busca, modo de permissão da conversa ativa e workspaces acessíveis.
 * Os setters vêm do useState (identidade estável); estão nas deps só para o lint.
 */
export function useChatEffects(st: ChatPageState, token: string) {
  const {
    streamStartedAt, setStreamElapsedMs, conversationsCollapsed, conversationSearch,
    setVisibleConversationCount, activeId, conversations, userDefaultPermissionMode,
    setPermissionModeState, setPermissionWarningRuntimeConfirmed, setProjectWorkspaces,
    setSelectedWorkspaceId,
  } = st

  // Tick do contador de tempo decorrido enquanto o stream está activo.
  useEffect(() => {
    if (streamStartedAt === null) return
    const id = window.setInterval(() => {
      setStreamElapsedMs(Date.now() - streamStartedAt)
    }, 200)
    return () => window.clearInterval(id)
  }, [streamStartedAt, setStreamElapsedMs])

  useEffect(() => {
    try {
      window.localStorage.setItem(
        CHAT_CONVERSATIONS_COLLAPSED_KEY,
        String(conversationsCollapsed),
      )
    } catch {
      // Preferência visual local não deve bloquear o chat.
    }
  }, [conversationsCollapsed])

  useEffect(() => {
    setVisibleConversationCount(CONVERSATION_PAGE_SIZE)
  }, [conversationSearch, setVisibleConversationCount])

  const activeConversationPermissionMode = useMemo(() => {
    const activeConversation = activeId
      ? conversations.find((conversation) => conversation.id === activeId)
      : null
    return activeConversation
      ? normalizePermissionMode(activeConversation.permission_mode)
      : userDefaultPermissionMode
  }, [activeId, conversations, userDefaultPermissionMode])

  useEffect(() => {
    setPermissionModeState(activeConversationPermissionMode)
    setPermissionWarningRuntimeConfirmed(false)
  }, [activeId, activeConversationPermissionMode, setPermissionModeState, setPermissionWarningRuntimeConfirmed])

  useEffect(() => {
    let cancelled = false
    fetchAccessibleWorkspaces(token)
      .then((list) => {
        if (cancelled) return
        setProjectWorkspaces(list)
        setSelectedWorkspaceId((prev) => defaultWorkspaceId(list, prev))
      })
      .catch(() => {})
    return () => { cancelled = true }
  }, [token, setProjectWorkspaces, setSelectedWorkspaceId])
}
