/**
 * ThinkingStream - sessao unica de pensamento do agente em tempo real.
 *
 * Substitui a pilha de cards individuais (Bash, Bash, Grep, Grep, Read...)
 * por um unico card que vai SOMANDO passos em ordem cronologica.
 *
 * UX:
 *   - Header sempre visivel com label dinamica (ultimo passo activo)
 *   - Auto-expandido durante streaming, auto-colapsado quando termina
 *   - Click no header alterna estado manualmente
 *   - Cada item entra com fade+slide (animacao no CSS)
 */

import { useState } from 'react'
import styles from './chat.module.css'
import {
  activeCoordinatorLabel,
  activeHeaderLabel,
  countByTool,
  displayToolName,
  formatElapsed,
} from './thinking-stream/labels'
import { ThinkingPhaseStep, ThinkingTextStep, ThinkingToolStep } from './thinking-stream/ThinkingSteps'
import type { ThoughtStep } from './thinking-stream/types'

export type { ThoughtStep } from './thinking-stream/types'

interface Props {
  steps: ThoughtStep[]
  /** True enquanto o stream gRPC continua emitindo eventos. */
  streaming: boolean
  /** Tempo decorrido em ms desde o início do stream (mostra no header). */
  elapsedMs?: number
  /** Tempo desde o último evento recebido do agente. */
  idleMs?: number
  interrupted?: boolean
}

export function ThinkingStream({
  steps,
  streaming,
  elapsedMs = 0,
  idleMs = 0,
  interrupted = false,
}: Props) {
  const [manualExpanded, setManualExpanded] = useState<boolean | null>(null)
  const [expandedToolId, setExpandedToolId] = useState<string | null>(null)

  // Auto-expand durante streaming; auto-colapso ao terminar.
  // ``manualExpanded ?? streaming`` já entrega esse comportamento sem
  // precisar de um useEffect (que viola react-hooks/set-state-in-effect):
  // enquanto o utilizador não toma controlo manual, ``expanded`` segue
  // ``streaming``, colapsando sozinho quando o turno termina.
  const expanded = manualExpanded ?? streaming

  if (steps.length === 0) return null

  const headerLabel = interrupted
    ? `Interrompido após ${formatElapsed(elapsedMs)}`
    : streaming
    ? activeHeaderLabel(steps, idleMs)
    : `Pensei por ${formatElapsed(elapsedMs)}`

  const toolCounts = countByTool(steps)
  const hasError = steps.some((s) => (s.kind === 'tool' || s.kind === 'phase') && s.isError)
  const coordinatorLabel = activeCoordinatorLabel(steps, idleMs)
  const actionCount = steps.filter((s) => s.kind !== 'phase').length

  return (
    <div
      className={`${styles.thinkingStream} ${
        streaming ? styles.thinkingStreamActive : ''
      } ${
        hasError ? styles.thinkingStreamError : ''
      }`}
    >
      <button
        type="button"
        className={styles.thinkingStreamHeader}
        onClick={() => setManualExpanded(!expanded)}
        aria-expanded={expanded}
        aria-label={`Linha de pensamento: ${headerLabel}. Clica para ${expanded ? 'colapsar' : 'expandir'}.`}
      >
        <span className={styles.thinkingStreamIcon} aria-hidden="true">
          {streaming ? (
            <span className={styles.thinkingStreamSpinner} />
          ) : interrupted || hasError ? (
            <span className={styles.thinkingStreamFailIcon}>!</span>
          ) : (
            <span className={styles.thinkingStreamDoneIcon}>✓</span>
          )}
        </span>

        <span className={styles.thinkingStreamHeaderMain}>
          <span className={styles.thinkingStreamHeaderTitle}>
            {headerLabel}
          </span>
          {toolCounts.length > 0 && (
            <span className={styles.thinkingStreamHeaderMeta}>
              {toolCounts.map(([name, n], i) => (
                <span key={name}>
                  {i > 0 && ' · '}
                  {displayToolName(name)} ×{n}
                </span>
              ))}
              {elapsedMs > 0 && (
                <span className={styles.thinkingStreamElapsed}>
                  {' · '}
                  {formatElapsed(elapsedMs)}
                </span>
              )}
            </span>
          )}
        </span>

        {actionCount > 0 && (
          <span className={styles.thinkingStreamCount}>
            {actionCount} {actionCount === 1 ? 'passo' : 'passos'}
          </span>
        )}
        <span className={styles.thinkingStreamChevron} aria-hidden="true">
          {expanded ? '▾' : '▸'}
        </span>
      </button>

      {expanded && (
        <div className={styles.thinkingStreamBody}>
          {steps.map((step, idx) => (
            <div
              key={step.id}
              className={styles.thinkingStreamStep}
              style={{ ['--cc-step-delay' as string]: `${Math.min(idx, 8) * 40}ms` }}
            >
              {step.kind === 'phase' ? (
                <ThinkingPhaseStep step={step} />
              ) : step.kind === 'text' ? (
                <ThinkingTextStep content={step.content} />
              ) : (
                <ThinkingToolStep
                  step={step}
                  expanded={expandedToolId === step.id}
                  onToggle={() =>
                    setExpandedToolId((curr) =>
                      curr === step.id ? null : step.id,
                    )
                  }
                />
              )}
            </div>
          ))}
          {streaming && (
            <div className={styles.thinkingStreamCoordinator} aria-live="polite">
              <span className={styles.thinkingStreamCoordinatorLine} />
              <span className={styles.thinkingStreamCoordinatorText}>
                {coordinatorLabel}
              </span>
              <span className={styles.thinkingStreamCoordinatorIdle}>
                {formatElapsed(idleMs)}
              </span>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
