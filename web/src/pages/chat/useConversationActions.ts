import { useCallback, useEffect } from 'react'
import {
  cancelConversation,
  createConversationPr,
  getToken,
  updateConversation,
  type Conversation,
} from '../../api'
import { randomId } from './formatting'
import type { AttachmentTrayState } from './useAttachmentTray'
import type { ChatPageState } from './useChatPageState'

/** Ações da sessão: parar, criar PR, nova conversa (Ctrl/Cmd+N), renomear, arquivar e selecionar. */
export function useConversationActions(
  st: ChatPageState,
  tray: Pick<AttachmentTrayState, 'setTrayItems' | 'setIsDragOver'>,
  token: string,
  closeMobile: () => void,
) {
  const {
    stopRequestedRef, streamStartedAt, streamElapsedMs, sessionProgressAnchor, activeId,
    abortControllerRef, setStreamStartedAt, setActivityTraces, setMessages, setStreaming,
    setPendingAction, setStreamActivityAt, setPrLoading, setPrError, setPrLinks, setHeadBranch,
    setMainMode, setActiveId, setMessagesError, setMessagesLoading, setSessionProgressAnchor,
    setPermissionModeState, userDefaultPermissionMode, setPermissionWarningRuntimeConfirmed, inputRef,
    setConversations, setArchivedRefreshKey, setThoughtSteps, setContextProgress, setSubagentGroups,
    setRuntimeStates, setInput,
  } = st
  const { setTrayItems, setIsDragOver } = tray

  async function handleStop() {
    if (stopRequestedRef.current) return
    stopRequestedRef.current = true
    const elapsedMs = streamStartedAt ? Date.now() - streamStartedAt : streamElapsedMs
    const anchor = sessionProgressAnchor
    const conversationId = activeId
    const cancelPromise = conversationId
      ? cancelConversation(token, conversationId)
      : Promise.resolve(false)
    abortControllerRef.current?.abort()
    setStreamStartedAt(null)
    if (anchor) {
      setActivityTraces((prev) => ({
        ...prev,
        [anchor.id]: {
          ...(prev[anchor.id] ?? { content: anchor.content, steps: [], elapsedMs: 0 }),
          content: anchor.content,
          elapsedMs,
          interrupted: true,
        },
      }))
      setMessages((m) => {
        const alreadyNotified = m.some(
          (msg) =>
            msg.role === 'assistant' &&
            msg.content === '_Execução interrompida antes da resposta final._',
        )
        if (alreadyNotified) return m
        return [
          ...m,
          {
            id: randomId(),
            role: 'assistant',
            content: '_Execução interrompida antes da resposta final._',
            created_at: new Date().toISOString(),
          },
        ]
      })
    }
    setStreaming(false)
    setPendingAction(null)
    setStreamActivityAt(null)
    try {
      await cancelPromise
    } finally {
      stopRequestedRef.current = false
    }
  }

  async function handleCreatePr() {
    if (!activeId) return
    setPrLoading(true)
    setPrError(null)
    try {
      const result = await createConversationPr(token, activeId)
      const perRepo = result.prs ?? []
      const opened = perRepo.filter((pr) => pr.pr_url)
      setPrLinks(
        opened.length > 0
          ? opened.map((pr) => ({ label: pr.alias || pr.slug, url: pr.pr_url as string }))
          : [{ label: '', url: result.pr_url }],
      )
      setHeadBranch(result.head_branch)
      const failed = perRepo.filter((pr) => pr.error)
      if (failed.length > 0) {
        setPrError(failed.map((pr) => `${pr.alias || pr.slug}: ${pr.error}`).join(' · '))
      }
    } catch (e) {
      setPrError(e instanceof Error ? e.message : 'Não foi possível criar o PR. Tente novamente.')
    } finally {
      setPrLoading(false)
    }
  }

  const handleNewChat = useCallback(() => {
    setMainMode('chat')
    closeMobile()
    setTrayItems([])
    setIsDragOver(false)
    setActiveId(null)
    setMessages([])
    setMessagesError(null)
    setMessagesLoading(false)
    setSessionProgressAnchor(null)
    setStreamActivityAt(null)
    setPermissionModeState(userDefaultPermissionMode)
    setPermissionWarningRuntimeConfirmed(false)
    setTimeout(() => inputRef.current?.focus(), 50)
    // Setters e refs têm identidade estável; listados só para o lint.
  }, [
    closeMobile, userDefaultPermissionMode, setMainMode, setTrayItems, setIsDragOver, setActiveId,
    setMessages, setMessagesError, setMessagesLoading, setSessionProgressAnchor, setStreamActivityAt,
    setPermissionModeState, setPermissionWarningRuntimeConfirmed, inputRef,
  ])

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === 'n') {
        e.preventDefault()
        handleNewChat()
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [handleNewChat])

  /** Seleciona uma conversa histórica sem deixar o streaming atual contaminar a UI. */
  async function handleRenameConversation(conversation: Conversation, title: string) {
    const token = getToken()
    if (!token) return
    const updated = await updateConversation(token, conversation.id, { title })
    setConversations((prev) => prev.map((item) => (item.id === updated.id ? { ...item, title: updated.title } : item)))
  }

  async function handleArchiveConversation(conversation: Conversation, archived: boolean) {
    const token = getToken()
    if (!token) return
    const updated = await updateConversation(token, conversation.id, { archived })
    setConversations((prev) =>
      prev.some((item) => item.id === updated.id)
        ? prev.map((item) => (item.id === updated.id ? { ...item, archived_at: updated.archived_at } : item))
        : [updated, ...prev],
    )
    setArchivedRefreshKey((key) => key + 1)
  }

  function handleOpenArchived(conversation: Conversation) {
    setConversations((prev) => (prev.some((item) => item.id === conversation.id) ? prev : [...prev, conversation]))
    handleSelectConversation(conversation.id)
  }

  function handleSelectConversation(conversationId: string) {
    setMainMode('chat')
    if (conversationId === activeId) return
    abortControllerRef.current?.abort()
    abortControllerRef.current = null
    setStreaming(false)
    setThoughtSteps([])
    setStreamActivityAt(null)
    setPendingAction(null)
    setSessionProgressAnchor(null)
    setContextProgress(null)
    setSubagentGroups([])
    setRuntimeStates([])
    setActivityTraces({})
    setInput('')
    setPermissionWarningRuntimeConfirmed(false)
    setActiveId(conversationId)
    closeMobile()
  }

  return {
    handleStop, handleCreatePr, handleNewChat, handleRenameConversation, handleArchiveConversation,
    handleOpenArchived, handleSelectConversation,
  }
}
