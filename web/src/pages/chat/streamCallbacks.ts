import type { ChatMessage, PayloadSizeBreakdown, StreamHandlers } from '../../api'
import {
  appendCommandStartToThoughts,
  appendTextToThoughts,
  appendToolStartToThoughts,
  applyCommandResultToThoughts,
  applyPhaseToThoughts,
  applyToolResultToThoughts,
  finishPendingThoughtTools,
} from '../../components/chat/thoughtSteps'
import { mergeSubagentGroup } from '../../components/chat/subagentGroups'
import { incrementStreamToolStats, randomId, updateActivityTrace } from './formatting'
import type { ChatPageState } from './useChatPageState'

/** Último diagnóstico de payload recebido no turno (anexado a mensagens de erro). */
export type PayloadDiagnosticsHolder = { current: PayloadSizeBreakdown | null }

/**
 * Handlers do stream do agente. Com `isActionResume` (resposta a uma ação
 * pendente) a timeline continua, mas o rastro por mensagem não é alterado.
 */
export function buildStreamHandlers({
  st, userMsg, isActionResume, payloadDiagnostics, signal,
}: {
  st: ChatPageState
  userMsg: ChatMessage
  isActionResume: boolean
  payloadDiagnostics: PayloadDiagnosticsHolder
  signal: AbortSignal
}): StreamHandlers {
  const {
    lastStreamCursorRef, lastTextOffsetRef, abortControllerRef, setStreamActivityAt, setThoughtSteps,
    setActivityTraces, setStreamToolStats, setPendingAction, setPermissionWarningRuntimeConfirmed,
    setContextProgress, setSubagentGroups, setRuntimeStates, setMessages, setLiveUsage,
  } = st
  return {
    onCursor(cursor) { lastStreamCursorRef.current = cursor },
    onText(accumulated) {
      setStreamActivityAt(Date.now())
      const delta = accumulated.slice(lastTextOffsetRef.current)
      lastTextOffsetRef.current = accumulated.length
      if (delta) {
        setThoughtSteps((prev) => appendTextToThoughts(prev, delta))
        if (!isActionResume) {
          setActivityTraces((prev) =>
            updateActivityTrace(prev, userMsg, (steps) => appendTextToThoughts(steps, delta)),
          )
        }
      }
    },
    onToolStart(tool) {
      setStreamActivityAt(Date.now())
      setStreamToolStats((prev) => incrementStreamToolStats(prev, tool.name))
      setThoughtSteps((prev) => appendToolStartToThoughts(prev, tool))
      if (!isActionResume) {
        setActivityTraces((prev) =>
          updateActivityTrace(prev, userMsg, (steps) => appendToolStartToThoughts(steps, tool)),
        )
      }
    },
    onToolResult(result) {
      setStreamActivityAt(Date.now())
      setThoughtSteps((prev) => applyToolResultToThoughts(prev, result))
      if (!isActionResume) {
        setActivityTraces((prev) =>
          updateActivityTrace(prev, userMsg, (steps) => applyToolResultToThoughts(steps, result)),
        )
      }
    },
    onCommandStart(event) {
      setStreamActivityAt(Date.now())
      setThoughtSteps((prev) => appendCommandStartToThoughts(prev, event))
      if (!isActionResume) {
        setActivityTraces((prev) =>
          updateActivityTrace(prev, userMsg, (steps) => appendCommandStartToThoughts(steps, event)),
        )
      }
    },
    onCommandResult(event) {
      setStreamActivityAt(Date.now())
      setThoughtSteps((prev) => applyCommandResultToThoughts(prev, event))
      if (!isActionResume) {
        setActivityTraces((prev) =>
          updateActivityTrace(prev, userMsg, (steps) => applyCommandResultToThoughts(steps, event)),
        )
      }
    },
    onActionRequired(action) {
      setStreamActivityAt(Date.now())
      setPendingAction(action)
      abortControllerRef.current?.abort()
    },
    onStatus(status) {
      setStreamActivityAt(Date.now())
      if (status.metadata?.permission_warning?.runtime_confirmed) {
        setPermissionWarningRuntimeConfirmed(true)
      }
      if (!status.stage) return
      const atMs = Date.now()
      setThoughtSteps((prev) => applyPhaseToThoughts(prev, status, atMs))
      if (!isActionResume) {
        setActivityTraces((prev) =>
          updateActivityTrace(prev, userMsg, (steps) => applyPhaseToThoughts(steps, status, atMs)),
        )
      }
    },
    onPayloadDiagnostic(diagnostics) {
      setStreamActivityAt(Date.now())
      payloadDiagnostics.current = diagnostics
    },
    onContextProgress(progress) {
      setStreamActivityAt(Date.now())
      setContextProgress(progress)
    },
    onSubagentGroup(group) {
      setStreamActivityAt(Date.now())
      setSubagentGroups((prev) => mergeSubagentGroup(prev, group, Date.now()))
    },
    onRuntimeState(state) {
      setStreamActivityAt(Date.now())
      setRuntimeStates((prev) => [...prev.slice(-3), state])
    },
    onError(message) {
      const atMs = Date.now()
      setStreamActivityAt(atMs)
      setThoughtSteps((prev) => finishPendingThoughtTools(prev, true, atMs))
      if (!isActionResume) {
        setActivityTraces((prev) =>
          updateActivityTrace(prev, userMsg, (steps) => finishPendingThoughtTools(steps, true, atMs)),
        )
      }
      setMessages((m) => [
        ...m,
        {
          id: randomId(),
          role: 'assistant',
          content: `**Erro:** ${message}`,
          created_at: new Date().toISOString(),
          payload_diagnostics: payloadDiagnostics.current,
        },
      ])
    },
    onDone(usage) {
      const atMs = Date.now()
      setStreamActivityAt(atMs)
      setLiveUsage(usage)
      setThoughtSteps((prev) => finishPendingThoughtTools(prev, false, atMs))
      if (!isActionResume) {
        setActivityTraces((prev) =>
          updateActivityTrace(prev, userMsg, (steps) => finishPendingThoughtTools(steps, false, atMs)),
        )
      }
    },
    signal,
  }
}
