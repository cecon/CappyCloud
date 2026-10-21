import {
  AuthError,
  fetchConversationDiff,
  fetchConversationUsage,
  fetchMessages,
  redirectToLogin,
  streamAssistantReply,
  type ChatMessage,
} from '../../api'
import type { TrayItem } from '../../components/AttachmentTray'
import { finishPendingThoughtTools } from '../../components/chat/thoughtSteps'
import { modelIdForAttachments, isSendableTrayItem, trayItemHasImage } from './attachments'
import { EMPTY_STREAM_TOOL_STATS, IMAGE_ONLY_PROMPT } from './constants'
import { randomId } from './formatting'
import { buildStreamHandlers, type PayloadDiagnosticsHolder } from './streamCallbacks'
import type { AttachmentTrayState } from './useAttachmentTray'
import type { ChatPageState } from './useChatPageState'
import type { ChatSelection } from './useChatSelection'

type SendMessageParams = {
  st: ChatPageState
  selection: ChatSelection
  tray: AttachmentTrayState
  token: string
  loadActivityHistory: (conversationId: string, msgs: ChatMessage[]) => Promise<void>
}

/** Envio de mensagem na conversa ativa e resposta a ações pendentes do agente. */
export function useSendMessage({ st, selection, tray, token, loadActivityHistory }: SendMessageParams) {
  const { permissionMode, onClaudeCli, claudeCliModelId } = selection
  const { trayItems, uploadPendingAttachments, clearTrayLocal } = tray
  const {
    pendingAction, activeId, streaming, input, models, selectedModelId, setSelectedModelId,
    lastStreamCursorRef, abortControllerRef, setInput, setStreaming, setThoughtSteps, lastTextOffsetRef,
    setStreamStartedAt, setStreamActivityAt, setStreamElapsedMs, setPendingAction, setContextProgress,
    setSubagentGroups, setRuntimeStates, setStreamToolStats, setPermissionWarningRuntimeConfirmed,
    setSessionProgressAnchor, setActivityTraces, setMessages, setConversations, executionProfile,
    setConvUsage, setLiveUsage, setDiffStats,
  } = st

  async function handleSend(textOverride?: string, options?: { resumeAction?: boolean }) {
    const isActionResume = Boolean(options?.resumeAction && pendingAction && textOverride?.trim())
    if (!activeId || (streaming && !isActionResume)) return
    const selectedPermissionMode = permissionMode

    // Bloqueia envio enquanto houver uploads em curso para não perder o
    // anexo no meio do streaming. Failed items podem ficar — o utilizador
    // já viu o erro e decide se remove ou tenta de novo.
    if (trayItems.some((it) => it.kind === 'uploading')) return
    const sendableAttachments = trayItems.filter(isSendableTrayItem)
    const text = (textOverride ?? input).trim() ||
      (sendableAttachments.length ? IMAGE_ONLY_PROMPT : '')
    if (!text) return
    // Claude CLI lê imagens direto; o modelo vem da escolha do Claude CLI.
    const modelForRequest = onClaudeCli
      ? claudeCliModelId
      : modelIdForAttachments(models, selectedModelId, sendableAttachments.some(trayItemHasImage))
    if (!onClaudeCli && modelForRequest && modelForRequest !== selectedModelId) {
      setSelectedModelId(modelForRequest)
    }
    const uploadedAttachmentIds = trayItems
      .filter((it): it is Extract<TrayItem, { kind: 'uploaded' }> => it.kind === 'uploaded')
      .map((it) => it.attachment.id)

    const resumeCursor = isActionResume ? lastStreamCursorRef.current : null
    if (!isActionResume) {
      lastStreamCursorRef.current = null
    }
    abortControllerRef.current?.abort()
    if (!textOverride) setInput('')
    setStreaming(true)
    if (!isActionResume) {
      setThoughtSteps([])
    }
    lastTextOffsetRef.current = 0
    const startedAt = Date.now()
    setStreamStartedAt(startedAt)
    setStreamActivityAt(startedAt)
    setStreamElapsedMs(0)
    setPendingAction(null)
      if (!isActionResume) {
        setContextProgress(null)
        setSubagentGroups([])
        setRuntimeStates([])
        setStreamToolStats(EMPTY_STREAM_TOOL_STATS)
      }
    setPermissionWarningRuntimeConfirmed(false)

    const ctrl = new AbortController()
    abortControllerRef.current = ctrl

    const userMsg: ChatMessage = {
      id: randomId(),
      role: 'user',
      content: text,
      created_at: new Date().toISOString(),
    }
    if (!isActionResume) {
      setSessionProgressAnchor({ id: userMsg.id, content: userMsg.content })
      setActivityTraces((prev) => ({
        ...prev,
        [userMsg.id]: { content: userMsg.content, steps: [], elapsedMs: 0 },
      }))
      setMessages((m) => [...m, userMsg])
    }
    const payloadDiagnostics: PayloadDiagnosticsHolder = { current: null }

    // Renomeia título se ainda for o default — bate com o backend.
    if (!isActionResume) {
      setConversations((prev) =>
      prev.map((c) => {
        if (c.id !== activeId) return c
        if (c.title && c.title !== 'Nova conversa') return c
        const previewTitle = text.length > 80 ? text.slice(0, 80) + '…' : text
        return { ...c, title: previewTitle, permission_mode: selectedPermissionMode }
      }),
      )
    }

    try {
      const pendingAttachmentIds = isActionResume ? [] : await uploadPendingAttachments(activeId)
      const attachmentIds = isActionResume ? [] : [...uploadedAttachmentIds, ...pendingAttachmentIds]
      await streamAssistantReply(
        token,
        activeId,
        text,
        buildStreamHandlers({ st, userMsg, isActionResume, payloadDiagnostics, signal: ctrl.signal }),
        modelForRequest || null,
        attachmentIds.length ? attachmentIds : null,
        selectedPermissionMode,
        executionProfile,
        resumeCursor,
        isActionResume,
      )
      setStreamStartedAt(null)
      setStreamActivityAt(null)
      setThoughtSteps((prev) => finishPendingThoughtTools(prev))
      if (!isActionResume) {
        setActivityTraces((prev) => ({
          ...prev,
          [userMsg.id]: {
            ...(prev[userMsg.id] ?? { content: userMsg.content, steps: [], elapsedMs: 0 }),
            content: userMsg.content,
            elapsedMs: Date.now() - startedAt,
          },
        }))
        clearTrayLocal()
      }
      const [msgs, totals] = await Promise.all([
        fetchMessages(token, activeId),
        fetchConversationUsage(token, activeId),
      ])
      setMessages(msgs)
      setConvUsage(totals)
      setLiveUsage(null)
      void loadActivityHistory(activeId, msgs)
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
      if (activeId) fetchConversationDiff(token, activeId).then((d) => setDiffStats(d.stats)).catch(() => {})
    }
  }

  function handleActionReply(reply: string) { void handleSend(reply, { resumeAction: true }) }

  return { handleSend, handleActionReply }
}
