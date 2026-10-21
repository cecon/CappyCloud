import { useCallback, useEffect } from 'react'
import {
  AuthError,
  errorToUserMessage,
  fetchConversationActivity,
  fetchConversationUsage,
  fetchMessages,
  redirectToLogin,
  type ChatMessage,
} from '../../api'
import { buildHistoryTraces } from '../../components/chat/thoughtSteps'
import type { ChatPageState } from './useChatPageState'

/**
 * Carrega mensagens, uso e timeline histórica da conversa ativa.
 * Setters e refs têm identidade estável; estão nas deps só para o lint.
 */
export function useConversationMessages(st: ChatPageState, token: string) {
  const {
    setActivityTraces, activeId, setMessages, setMessagesLoading, setMessagesError, setConvUsage,
    setLiveUsage, optimisticConversationIdRef, setDiffStats, setPrLinks, setHeadBranch,
  } = st

  /** Reconstrói a timeline de ações de cada turno a partir do histórico do servidor. */
  const loadActivityHistory = useCallback(
    async (conversationId: string, msgs: ChatMessage[]) => {
      try {
        const turns = await fetchConversationActivity(token, conversationId)
        const traces = buildHistoryTraces(turns, msgs)
        setActivityTraces((prev) => ({ ...prev, ...traces }))
      } catch (e) {
        if (e instanceof AuthError) redirectToLogin()
        // Sem histórico a conversa continua utilizável; só a timeline antiga não aparece.
      }
    },
    [token, setActivityTraces],
  )

  useEffect(() => {
    if (!activeId) {
      setMessages([])
      setMessagesLoading(false)
      setMessagesError(null)
      setConvUsage({ total_prompt_tokens: 0, total_completion_tokens: 0, total_cost_usd: 0 })
      setLiveUsage(null)
      return
    }
    let cancelled = false
    const preserveOptimistic = optimisticConversationIdRef.current === activeId
    setDiffStats(null)
    setPrLinks([])
    setHeadBranch(null)
    if (!preserveOptimistic) {
      setMessages([])
      setMessagesLoading(true)
    } else {
      setMessagesLoading(false)
    }
    setMessagesError(null)
    setLiveUsage(null)
    ;(async () => {
      try {
        const [msgs, usage] = await Promise.all([
          fetchMessages(token, activeId),
          fetchConversationUsage(token, activeId),
        ])
        if (!cancelled) {
          setMessages((prev) =>
            preserveOptimistic && msgs.length === 0 && prev.length > 0 ? prev : msgs,
          )
          setConvUsage(usage)
          // Na conversa recém-criada a timeline ao vivo é a fonte; o histórico
          // é recarregado quando o turno termina.
          if (!preserveOptimistic) void loadActivityHistory(activeId, msgs)
        }
      } catch (e) {
        if (e instanceof AuthError) {
          redirectToLogin()
          return
        }
        if (!cancelled) setMessagesError(errorToUserMessage(e))
      } finally {
        if (!cancelled) setMessagesLoading(false)
      }
    })()
    return () => { cancelled = true }
  }, [
    activeId, token, loadActivityHistory, setMessages, setMessagesLoading, setMessagesError, setConvUsage,
    setLiveUsage, optimisticConversationIdRef, setDiffStats, setPrLinks, setHeadBranch,
  ])

  return loadActivityHistory
}
