/**
 * Redutores da timeline de atividade do agente.
 *
 * Usados tanto pelo stream ao vivo (SSE) quanto pela reconstrução do histórico
 * (GET /conversations/:id/activity), para a timeline de um turno antigo ser
 * idêntica à que o utilizador viu enquanto ele acontecia.
 */

import {
  parseStatusEvent,
  type CommandResultEvent,
  type CommandResultStatus,
  type CommandStartEvent,
  type ConversationActivityTurn,
  type StatusEvent,
} from '../../api'
import type { ThoughtStep } from '../ThinkingStream'

type PhaseStep = Extract<ThoughtStep, { kind: 'phase' }>

/**
 * Concatena chunks de texto consecutivos no último step de tipo 'text' para
 * preservar a ordem natural texto→tool→texto→tool→… Quando chega um tool_start,
 * congela o texto atual e abre um novo step de tool. Tool_result actualiza o
 * step correspondente.
 */
export function appendTextToThoughts(prev: ThoughtStep[], delta: string): ThoughtStep[] {
  if (!delta) return prev
  const last = prev[prev.length - 1]
  if (last && last.kind === 'text') {
    return [...prev.slice(0, -1), { ...last, content: last.content + delta }]
  }
  return [...prev, { kind: 'text', id: `t-${prev.length}-${Date.now()}`, content: delta }]
}

export function appendToolStartToThoughts(
  prev: ThoughtStep[],
  tool: { id: string; name: string; input: string },
): ThoughtStep[] {
  if (!tool.id || !tool.name) return prev
  if (prev.some((s) => s.kind === 'tool' && s.id === tool.id)) return prev
  return [...prev, { kind: 'tool', id: tool.id, name: tool.name, input: tool.input, done: false }]
}

export function applyToolResultToThoughts(
  prev: ThoughtStep[],
  result: { id: string; output: string; is_error: boolean },
): ThoughtStep[] {
  if (!result.id) return prev
  return prev.map((step) =>
    step.kind === 'tool' && step.id === result.id
      ? { ...step, output: result.output, isError: result.is_error, done: true }
      : step,
  )
}

function commandThoughtId(command: string): string {
  return `command:${command || 'unknown'}`
}

export function appendCommandStartToThoughts(
  prev: ThoughtStep[],
  event: CommandStartEvent,
): ThoughtStep[] {
  const id = commandThoughtId(event.command)
  if (prev.some((step) => step.kind === 'tool' && step.id === id)) return prev
  return [
    ...prev,
    { kind: 'tool', id, name: event.command || 'comando', input: event.label, done: false },
  ]
}

export function applyCommandResultToThoughts(
  prev: ThoughtStep[],
  event: CommandResultEvent,
): ThoughtStep[] {
  const id = commandThoughtId(event.command)
  const isError =
    event.status === 'failed' || event.status === 'cancelled' || event.status === 'unavailable'
  const output = event.details_markdown || event.summary
  if (prev.some((step) => step.kind === 'tool' && step.id === id)) {
    return prev.map((step) =>
      step.kind === 'tool' && step.id === id ? { ...step, output, isError, done: true } : step,
    )
  }
  return [
    ...prev,
    {
      kind: 'tool',
      id,
      name: event.command || 'comando',
      input: 'Comando do chat',
      output,
      isError,
      done: true,
    },
  ]
}

/**
 * Abre ou fecha uma fase real do turno (workspace, contexto, modelo).
 * `atMs` é o instante do evento: relógio local no stream, `created_at` no histórico.
 */
export function applyPhaseToThoughts(
  prev: ThoughtStep[],
  status: StatusEvent,
  atMs: number,
): ThoughtStep[] {
  const stage = status.stage
  if (!stage) return prev
  const openIndex = findLastIndex(prev, (s) => s.kind === 'phase' && s.stage === stage && !s.done)
  const reportedMs = status.metadata?.duration_ms

  if (status.state === 'done') {
    if (openIndex >= 0) {
      const open = prev[openIndex] as PhaseStep
      const closed: PhaseStep = {
        ...open,
        label: status.message,
        done: true,
        durationMs: reportedMs ?? Math.max(0, atMs - open.startedAt),
      }
      return [...prev.slice(0, openIndex), closed, ...prev.slice(openIndex + 1)]
    }
    return [
      ...prev,
      {
        kind: 'phase',
        id: `phase:${stage}:${prev.length}`,
        stage,
        label: status.message,
        done: true,
        startedAt: atMs - (reportedMs ?? 0),
        durationMs: reportedMs,
      },
    ]
  }

  if (openIndex >= 0) {
    const open = prev[openIndex] as PhaseStep
    return [
      ...prev.slice(0, openIndex),
      { ...open, label: status.message },
      ...prev.slice(openIndex + 1),
    ]
  }
  return [
    ...prev,
    {
      kind: 'phase',
      id: `phase:${stage}:${prev.length}`,
      stage,
      label: status.message,
      done: false,
      startedAt: atMs,
    },
  ]
}

/** Fecha ferramentas e fases pendentes quando o turno termina (ou falha). */
export function finishPendingThoughtTools(
  prev: ThoughtStep[],
  isError = false,
  atMs?: number,
): ThoughtStep[] {
  return prev.map((step) => {
    if (step.kind === 'tool' && !step.done) {
      return { ...step, done: true, isError: isError || step.isError, output: step.output ?? '' }
    }
    if (step.kind === 'phase' && !step.done) {
      return {
        ...step,
        done: true,
        isError: isError || step.isError,
        durationMs: atMs !== undefined ? Math.max(0, atMs - step.startedAt) : step.durationMs,
      }
    }
    return step
  })
}

export type ReplayedTrace = {
  steps: ThoughtStep[]
  elapsedMs: number
  interrupted: boolean
}

const COMMAND_STATUSES: readonly CommandResultStatus[] = [
  'started',
  'waiting_for_input',
  'completed',
  'unavailable',
  'failed',
  'cancelled',
]

/** Reconstrói a timeline de um turno a partir dos eventos gravados no servidor. */
export function replayActivityTurn(turn: ConversationActivityTurn): ReplayedTrace {
  let steps: ThoughtStep[] = []
  let interrupted = false
  const startedMs = Date.parse(turn.created_at)
  let lastMs = startedMs

  for (const event of turn.events) {
    const atMs = event.at ? Date.parse(event.at) : lastMs
    lastMs = atMs
    const data = event.data
    switch (event.type) {
      case 'text':
        steps = appendTextToThoughts(steps, String(data.content ?? ''))
        break
      case 'tool_start':
        steps = appendToolStartToThoughts(steps, {
          id: String(data.id ?? ''),
          name: String(data.name ?? ''),
          input: String(data.input ?? ''),
        })
        break
      case 'tool_result':
        steps = applyToolResultToThoughts(steps, {
          id: String(data.id ?? ''),
          output: String(data.output ?? ''),
          is_error: data.is_error === true,
        })
        break
      case 'command_start':
        steps = appendCommandStartToThoughts(steps, {
          command: String(data.command ?? ''),
          label: String(data.label ?? 'Comando iniciado'),
        })
        break
      case 'command_result': {
        const status = COMMAND_STATUSES.find((s) => s === data.status) ?? 'failed'
        steps = applyCommandResultToThoughts(steps, {
          command: String(data.command ?? ''),
          status,
          summary: String(data.summary ?? 'Comando finalizado.'),
          details_markdown: (data.details_markdown as string | null) ?? null,
        })
        break
      }
      case 'status':
        steps = applyPhaseToThoughts(steps, parseStatusEvent(data), atMs)
        break
      case 'error':
        steps = [
          ...finishPendingThoughtTools(steps, true, atMs),
          {
            kind: 'phase',
            id: `phase:error:${steps.length}`,
            stage: 'error',
            label: String(data.message ?? 'Erro desconhecido'),
            done: true,
            isError: true,
            startedAt: atMs,
          },
        ]
        break
      case 'canceled':
      case 'stalled':
      case 'permission_timeout':
        interrupted = true
        steps = finishPendingThoughtTools(steps, false, atMs)
        break
      case 'done':
        steps = finishPendingThoughtTools(steps, false, atMs)
        break
    }
  }

  const endIso = turn.completed_at ?? turn.last_event_at
  const endMs = endIso ? Date.parse(endIso) : lastMs
  if (turn.status === 'canceled' || turn.status === 'cancelled') interrupted = true
  return {
    steps: finishPendingThoughtTools(steps, false, endMs),
    elapsedMs: Math.max(0, endMs - startedMs),
    interrupted,
  }
}

export type HistoryTrace = ReplayedTrace & { content: string }

/**
 * Agrupa os turnos do histórico por mensagem do utilizador. Um mesmo pedido
 * pode ter mais de um turno (ex.: resposta a uma confirmação); os passos são
 * concatenados na ordem em que aconteceram.
 */
export function buildHistoryTraces(
  turns: ConversationActivityTurn[],
  messages: Array<{ id: string; role: string; content: string }>,
): Record<string, HistoryTrace> {
  const contentById = new Map(
    messages.filter((m) => m.role === 'user').map((m) => [m.id, m.content]),
  )
  const traces: Record<string, HistoryTrace> = {}
  for (const turn of turns) {
    const messageId = turn.user_message_id
    if (!messageId || !contentById.has(messageId)) continue
    const replayed = replayActivityTurn(turn)
    if (replayed.steps.length === 0) continue
    const current = traces[messageId]
    traces[messageId] = current
      ? {
          content: current.content,
          steps: [...current.steps, ...replayed.steps],
          elapsedMs: current.elapsedMs + replayed.elapsedMs,
          interrupted: replayed.interrupted,
        }
      : { content: contentById.get(messageId) ?? '', ...replayed }
  }
  return traces
}

function findLastIndex<T>(items: T[], predicate: (item: T) => boolean): number {
  for (let index = items.length - 1; index >= 0; index -= 1) {
    if (predicate(items[index])) return index
  }
  return -1
}
