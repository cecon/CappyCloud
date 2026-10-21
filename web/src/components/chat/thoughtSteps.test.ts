import { describe, expect, it } from 'vitest'
import type { ConversationActivityTurn } from '../../api'
import { applyPhaseToThoughts, buildHistoryTraces, replayActivityTurn } from './thoughtSteps'

const T0 = Date.parse('2026-09-23T12:00:00Z')
const iso = (seconds: number) => new Date(T0 + seconds * 1000).toISOString()

function turn(overrides: Partial<ConversationActivityTurn> = {}): ConversationActivityTurn {
  return {
    task_id: 't1',
    user_message_id: 'm1',
    status: 'done',
    model_used: 'modelo',
    created_at: iso(0),
    completed_at: iso(20),
    last_event_at: iso(20),
    events: [],
    ...overrides,
  }
}

describe('applyPhaseToThoughts', () => {
  it('abre e fecha a fase usando a duração informada pelo backend', () => {
    const opened = applyPhaseToThoughts(
      [],
      { message: 'Preparando workspace: Seller', stage: 'workspace', state: 'active' },
      T0,
    )
    const closed = applyPhaseToThoughts(
      opened,
      {
        message: 'Workspace pronto: Seller',
        stage: 'workspace',
        state: 'done',
        metadata: { duration_ms: 1234 },
      },
      T0 + 5000,
    )

    expect(closed).toEqual([
      expect.objectContaining({
        kind: 'phase',
        stage: 'workspace',
        label: 'Workspace pronto: Seller',
        done: true,
        durationMs: 1234,
      }),
    ])
  })

  it('ignora status sem fase', () => {
    expect(applyPhaseToThoughts([], { message: 'heartbeat' }, T0)).toEqual([])
  })
})

describe('replayActivityTurn', () => {
  it('reconstrói fases, texto e ferramentas na ordem real', () => {
    const replayed = replayActivityTurn(
      turn({
        events: [
          { type: 'status', data: { stage: 'context', state: 'active', message: 'Preparando contexto' }, at: iso(0) },
          { type: 'status', data: { stage: 'context', state: 'done', message: 'Contexto preparado' }, at: iso(3) },
          { type: 'status', data: { stage: 'agent', state: 'active', message: 'Aguardando' }, at: iso(3) },
          { type: 'text', data: { content: 'Vou ler o arquivo.' }, at: iso(8) },
          { type: 'status', data: { stage: 'agent', state: 'done', message: 'Modelo respondeu' }, at: iso(8) },
          { type: 'tool_start', data: { id: 'x', name: 'Read', input: '{}' }, at: iso(9) },
          { type: 'tool_result', data: { id: 'x', output: 'conteúdo', is_error: false }, at: iso(10) },
          { type: 'done', data: {}, at: iso(20) },
        ],
      }),
    )

    expect(replayed.steps.map((s) => s.kind)).toEqual(['phase', 'phase', 'text', 'tool'])
    expect(replayed.steps[0]).toMatchObject({ label: 'Contexto preparado', durationMs: 3000 })
    expect(replayed.steps[1]).toMatchObject({ label: 'Modelo respondeu', durationMs: 5000 })
    expect(replayed.steps[3]).toMatchObject({ done: true, output: 'conteúdo' })
    expect(replayed.elapsedMs).toBe(20000)
    expect(replayed.interrupted).toBe(false)
  })

  it('marca erro como fase de erro e fecha pendências', () => {
    const replayed = replayActivityTurn(
      turn({
        status: 'error',
        events: [
          { type: 'tool_start', data: { id: 'x', name: 'Bash', input: '{}' }, at: iso(1) },
          { type: 'error', data: { message: 'provider caiu' }, at: iso(2) },
        ],
      }),
    )

    expect(replayed.steps[0]).toMatchObject({ kind: 'tool', done: true, isError: true })
    expect(replayed.steps[1]).toMatchObject({ kind: 'phase', stage: 'error', label: 'provider caiu' })
  })
})

describe('buildHistoryTraces', () => {
  it('agrupa turnos por mensagem e ignora mensagens desconhecidas', () => {
    const textEvent = { type: 'text', data: { content: 'oi' }, at: iso(1) }
    const traces = buildHistoryTraces(
      [
        turn({ task_id: 'a', events: [textEvent] }),
        turn({ task_id: 'b', events: [textEvent] }),
        turn({ task_id: 'c', user_message_id: 'outra', events: [textEvent] }),
      ],
      [{ id: 'm1', role: 'user', content: 'olá' }],
    )

    expect(Object.keys(traces)).toEqual(['m1'])
    expect(traces.m1.content).toBe('olá')
    expect(traces.m1.steps).toHaveLength(2)
    expect(traces.m1.elapsedMs).toBe(40000)
  })
})
