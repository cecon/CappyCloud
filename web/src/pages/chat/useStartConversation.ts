import {
  AuthError,
  createConversation,
  errorToUserMessage,
  fetchConversationDiff,
  fetchConversationUsage,
  fetchMessages,
  redirectToLogin,
  streamAssistantReply,
  type ChatMessage,
} from '../../api'
import { finishPendingThoughtTools } from '../../components/chat/thoughtSteps'
import { modelIdForAttachments, isSendableTrayItem, trayItemHasImage } from './attachments'
import { EMPTY_STREAM_TOOL_STATS, IMAGE_ONLY_PROMPT } from './constants'
import { randomId } from './formatting'
import { rememberWorkspace } from './preferences'
import { buildStreamHandlers, type PayloadDiagnosticsHolder } from './streamCallbacks'
import type { AttachmentTrayState } from './useAttachmentTray'
import type { ChatPageState } from './useChatPageState'
import type { ChatSelection } from './useChatSelection'

type StartConversationParams = {
  st: ChatPageState
  selection: ChatSelection
  tray: AttachmentTrayState
  token: string
  loadActivityHistory: (conversationId: string, msgs: ChatMessage[]) => Promise<void>
}

/** Cria conversa e envia a mensagem inicial de uma vez */
export function useStartConversation({ st, selection, tray, token, loadActivityHistory }: StartConversationParams) {
  const { permissionMode, onClaudeCli, claudeCliModelId } = selection
  const { trayItems, uploadPendingAttachments, clearTrayLocal } = tray
  const {
    models, selectedModelId, setSelectedModelId, selectedWorkspaceId, setNewChatError, ticketNumber,
    setTicketNumber, optimisticConversationIdRef, setConversations, setActiveId, setMessages, setInput,
    setStreaming, setThoughtSteps, lastTextOffsetRef, setStreamStartedAt, setStreamActivityAt,
    setStreamElapsedMs, setPendingAction, setContextProgress, setSubagentGroups, setRuntimeStates,
    setStreamToolStats, setPermissionWarningRuntimeConfirmed, abortControllerRef,
    setSessionProgressAnchor, setActivityTraces, executionProfile, setConvUsage, setLiveUsage, setDiffStats,
  } = st

  async function handleNewChatWithMessage(text: string) {
    const selectedPermissionMode = permissionMode
    const sendableAttachments = trayItems.filter(isSendableTrayItem)
    const userText = text.trim() || (sendableAttachments.length ? IMAGE_ONLY_PROMPT : '')
    if (!userText) return
    // Claude CLI lê imagens direto; o modelo vem da escolha do Claude CLI.
    const modelForRequest = onClaudeCli
      ? claudeCliModelId
      : modelIdForAttachments(models, selectedModelId, sendableAttachments.some(trayItemHasImage))
    if (!onClaudeCli && modelForRequest && modelForRequest !== selectedModelId) {
      setSelectedModelId(modelForRequest)
    }
    // Conversa nova é sempre de um workspace (a sandbox e os repositórios vêm dele).
    if (!selectedWorkspaceId) {
      setNewChatError('Selecione um workspace para começar a conversa.')
      return
    }
    let c
    try {
      setNewChatError(null)
      rememberWorkspace(selectedWorkspaceId)
      c = await createConversation(
        token,
        [],
        modelForRequest || null,
        null,
        selectedWorkspaceId,
        ticketNumber.trim() || null,
      )
      setTicketNumber('')
    } catch (err) {
      if (err instanceof AuthError) {
        redirectToLogin()
        return
      }
      setNewChatError(errorToUserMessage(err))
      return
    }
    // Update otimista do título — o backend renomeia "Nova conversa" para o
    // início da primeira mensagem (mesma lógica de _TITLE_MAX_LEN=80).
    const previewTitle =
      userText.length > 80 ? userText.slice(0, 80) + '…' : userText
    const cWithTitle = { ...c, title: previewTitle, permission_mode: selectedPermissionMode }
    optimisticConversationIdRef.current = c.id
    setConversations((prev) => [cWithTitle, ...prev])
    setActiveId(c.id)
    setMessages([])
    setInput('')

    setStreaming(true)
    setThoughtSteps([])
    lastTextOffsetRef.current = 0
    const startedAt = Date.now()
    setStreamStartedAt(startedAt)
    setStreamActivityAt(startedAt)
    setStreamElapsedMs(0)
    setPendingAction(null)
    setContextProgress(null)
    setSubagentGroups([])
    setRuntimeStates([])
    setStreamToolStats(EMPTY_STREAM_TOOL_STATS)
    setPermissionWarningRuntimeConfirmed(false)

    const ctrl = new AbortController()
    abortControllerRef.current = ctrl

    const userMsg: ChatMessage = {
      id: randomId(),
      role: 'user',
      content: userText,
      created_at: new Date().toISOString(),
    }
    setSessionProgressAnchor({ id: userMsg.id, content: userMsg.content })
    setActivityTraces((prev) => ({
      ...prev,
      [userMsg.id]: { content: userMsg.content, steps: [], elapsedMs: 0 },
    }))
    setMessages([userMsg])
    const payloadDiagnostics: PayloadDiagnosticsHolder = { current: null }

    try {
      const uploadedAttachmentIds = await uploadPendingAttachments(c.id)
      await streamAssistantReply(
        token,
        c.id,
        userText,
        buildStreamHandlers({ st, userMsg, isActionResume: false, payloadDiagnostics, signal: ctrl.signal }),
        modelForRequest || null,
        uploadedAttachmentIds.length ? uploadedAttachmentIds : null,
        selectedPermissionMode,
        executionProfile,
        null,
        false,
      )
      setStreamStartedAt(null)
      setStreamActivityAt(null)
      setThoughtSteps((prev) => finishPendingThoughtTools(prev))
      setActivityTraces((prev) => ({
        ...prev,
        [userMsg.id]: {
          ...(prev[userMsg.id] ?? { content: userMsg.content, steps: [], elapsedMs: 0 }),
          content: userMsg.content,
          elapsedMs: Date.now() - startedAt,
        },
      }))
      clearTrayLocal()
      const [msgs, totals] = await Promise.all([
        fetchMessages(token, c.id),
        fetchConversationUsage(token, c.id),
      ])
      setMessages(msgs)
      optimisticConversationIdRef.current = null
      setConvUsage(totals)
      setLiveUsage(null)
      void loadActivityHistory(c.id, msgs)
    } catch (e) {
      if (e instanceof AuthError) {
        redirectToLogin(); return
      } else if (e instanceof Error && e.name === 'AbortError') {
        // Cancelled by user — silently finalize
      } else {
        setMessages((m) => [
          ...m,
          {
            id: randomId(),
            role: 'assistant',
            content: `**Erro:** ${e instanceof Error ? e.message : String(e)}`,
            created_at: new Date().toISOString(),
            payload_diagnostics: payloadDiagnostics.current,
          },
        ])
      }
    } finally {
      setStreaming(false)
      setStreamStartedAt(null)
      setStreamActivityAt(null)
      setThoughtSteps((prev) => finishPendingThoughtTools(prev))
      abortControllerRef.current = null
      fetchConversationDiff(token, c.id).then((d) => setDiffStats(d.stats)).catch(() => {})
    }
  }

  return handleNewChatWithMessage
}
