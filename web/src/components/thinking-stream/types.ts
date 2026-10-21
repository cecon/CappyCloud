import type { TurnPhaseStage } from '../../api'

export type ThoughtStep =
  | {
      kind: 'text'
      id: string
      content: string
    }
  | {
      kind: 'tool'
      id: string
      name: string
      input: string
      output?: string
      isError?: boolean
      done: boolean
    }
  | {
      /** Fase real do turno (workspace, contexto, modelo) ou erro terminal. */
      kind: 'phase'
      id: string
      stage: TurnPhaseStage | 'error'
      label: string
      done: boolean
      startedAt: number
      durationMs?: number
      isError?: boolean
    }
