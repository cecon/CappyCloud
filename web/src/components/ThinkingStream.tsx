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

interface Props {
  steps: ThoughtStep[]
  /** True enquanto o stream gRPC continua emitindo eventos. */
  streaming: boolean
  /** Tempo decorrido em ms desde o inicio do stream (mostra no header). */
  elapsedMs?: number
  /** Tempo desde o ultimo evento recebido do agente. */
  idleMs?: number
  interrupted?: boolean
}

function summarizeToolInput(name: string, raw: string): string {
  let parsed: Record<string, unknown> | null = null
  try {
    parsed = JSON.parse(raw)
  } catch {
    parsed = null
  }
  if (!parsed) return raw.slice(0, 80)

  const lname = name.toLowerCase()
  if (lname === 'grep') {
    const pattern = String(parsed.pattern ?? '')
    const path = String(parsed.path ?? parsed.glob ?? '')
    return path ? `"${pattern}" em ${path}` : `"${pattern}"`
  }
  if (lname === 'read') {
    return String(parsed.file_path ?? parsed.path ?? raw)
  }
  if (lname === 'bash') {
    return String(parsed.command ?? '')
  }
  if (lname === 'glob') {
    return String(parsed.pattern ?? '')
  }
  if (lname === 'edit' || lname === 'write') {
    return String(parsed.file_path ?? parsed.path ?? '')
  }
  if (lname === 'webfetch' || lname === 'web_fetch') {
    return String(parsed.url ?? '')
  }
  const firstStrVal = Object.values(parsed).find(
    (v) => typeof v === 'string' && (v as string).length > 0,
  )
  return firstStrVal ? String(firstStrVal).slice(0, 80) : ''
}

function describeActiveStep(step: ThoughtStep): string {
  if (step.kind === 'text') {
    const trimmed = step.content.trim().replace(/\s+/g, ' ')
    return trimmed.length > 80 ? `${trimmed.slice(0, 80)}...` : trimmed || 'Pensando...'
  }
  const lname = step.name.toLowerCase()
  const summary = summarizeToolInput(step.name, step.input)
  const verb =
    lname === 'grep'
      ? 'Pesquisando'
      : lname === 'read'
        ? 'Lendo'
        : lname === 'bash'
          ? 'Executando'
          : lname === 'glob'
            ? 'Listando'
            : lname === 'edit' || lname === 'write'
              ? 'Editando'
              : lname === 'webfetch' || lname === 'web_fetch'
                ? 'Buscando'
                : step.name
  return summary ? `${verb} ${summary}` : verb
}

function formatElapsed(ms: number): string {
  if (ms < 1000) return `${ms}ms`
  const s = ms / 1000
  if (s < 60) return `${s.toFixed(1)}s`
  const m = Math.floor(s / 60)
  return `${m}m${Math.round(s - m * 60)}s`
}

function countByTool(steps: ThoughtStep[]): Array<[string, number]> {
  const counts: Record<string, number> = {}
  for (const s of steps) {
    if (s.kind !== 'tool') continue
    counts[s.name] = (counts[s.name] ?? 0) + 1
  }
  return Object.entries(counts).sort((a, b) => b[1] - a[1])
}

function activeCoordinatorLabel(steps: ThoughtStep[], idleMs: number): string {
  const runningTools = steps.filter(
    (s): s is Extract<ThoughtStep, { kind: 'tool' }> => s.kind === 'tool' && !s.done,
  )
  if (runningTools.length > 1) {
    return `Aguardando ${runningTools.length} ferramentas em paralelo`
  }
  if (runningTools.length === 1) {
    return `Aguardando ${runningTools[0].name}`
  }
  if (idleMs < 8_000) return 'Pensando'
  if (idleMs < 35_000) return 'Consolidando evidencias'
  if (idleMs < 90_000) return 'Aguardando coordenador'
  return 'Preparando resposta final'
}

function activeHeaderLabel(steps: ThoughtStep[], idleMs: number): string {
  const runningTools = steps.filter(
    (s): s is Extract<ThoughtStep, { kind: 'tool' }> => s.kind === 'tool' && !s.done,
  )
  if (runningTools.length > 1) return `${runningTools.length} ferramentas trabalhando em paralelo`
  if (runningTools.length === 1) return describeActiveStep(runningTools[0])
  if (idleMs < 8_000) return 'Pensando...'
  if (idleMs < 35_000) return 'Cruzando resultados das ferramentas...'
  if (idleMs < 90_000) return 'Aguardando o coordenador continuar...'
  return 'Aguardando a resposta final...'
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
  // ``manualExpanded ?? streaming`` ja entrega esse comportamento sem
  // precisar de um useEffect (que viola react-hooks/set-state-in-effect):
  // enquanto o utilizador nao toma controlo manual, ``expanded`` segue
  // ``streaming``, colapsando sozinho quando o turno termina.
  const expanded = manualExpanded ?? streaming

  if (steps.length === 0) return null

  const headerLabel = interrupted
    ? `Interrompido apos ${formatElapsed(elapsedMs)}`
    : streaming
    ? activeHeaderLabel(steps, idleMs)
    : `Pensei por ${formatElapsed(elapsedMs)}`

  const toolCounts = countByTool(steps)
  const hasError = steps.some((s) => s.kind === 'tool' && s.isError)
  const coordinatorLabel = activeCoordinatorLabel(steps, idleMs)

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
            <span className={styles.thinkingStreamDoneIcon}>ok</span>
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
                  {i > 0 && ' - '}
                  {name} x{n}
                </span>
              ))}
              {elapsedMs > 0 && (
                <span className={styles.thinkingStreamElapsed}>
                  {' - '}
                  {formatElapsed(elapsedMs)}
                </span>
              )}
            </span>
          )}
        </span>

        <span className={styles.thinkingStreamCount}>
          {steps.length} {steps.length === 1 ? 'passo' : 'passos'}
        </span>
        <span className={styles.thinkingStreamChevron} aria-hidden="true">
          {expanded ? 'v' : '>'}
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
              {step.kind === 'text' ? (
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

function ThinkingTextStep({ content }: { content: string }) {
  const trimmed = content.trim()
  if (!trimmed) return null
  return (
    <div className={styles.thinkingStreamTextStep}>
      <span className={styles.thinkingStreamTextIcon} aria-hidden="true">
        ●
      </span>
      <div className={styles.thinkingStreamTextBody}>{trimmed}</div>
    </div>
  )
}

function ThinkingToolStep({
  step,
  expanded,
  onToggle,
}: {
  step: Extract<ThoughtStep, { kind: 'tool' }>
  expanded: boolean
  onToggle: () => void
}) {
  const summary = summarizeToolInput(step.name, step.input)
  const stateClass = step.isError
    ? styles.thinkingStreamToolError
    : step.done
      ? ''
      : styles.thinkingStreamToolRunning

  let prettyInput = step.input
  try {
    prettyInput = JSON.stringify(JSON.parse(step.input), null, 2)
  } catch {
    /* keep raw */
  }

  return (
    <div
      className={`${styles.thinkingStreamToolStep} ${
        !step.done ? styles.thinkingStreamToolStepRunning : ''
      } ${step.isError ? styles.thinkingStreamToolStepError : ''}`}
    >
      <button
        type="button"
        className={`${styles.thinkingStreamToolHeader} ${stateClass}`}
        onClick={onToggle}
        aria-expanded={expanded}
      >
        <span className={styles.thinkingStreamToolMark} aria-hidden="true">
          {step.isError ? 'x' : step.done ? '>' : '...'}
        </span>
        <span className={styles.thinkingStreamToolName}>{step.name}</span>
        <span className={styles.thinkingStreamToolSummary}>{summary}</span>
        <span className={styles.thinkingStreamToolChevron} aria-hidden="true">
          {expanded ? '-' : '+'}
        </span>
      </button>

      {expanded && (
        <div className={styles.thinkingStreamToolDetail}>
          <div>
            <div className={styles.thinkingStreamToolDetailLabel}>Entrada</div>
            <pre className={styles.thinkingStreamToolPre}>{prettyInput}</pre>
          </div>
          {step.output !== undefined && (
            <div>
              <div className={styles.thinkingStreamToolDetailLabel}>
                {step.isError ? 'Saida (erro)' : 'Saida'}
              </div>
              <pre
                className={`${styles.thinkingStreamToolPre} ${
                  step.isError ? styles.thinkingStreamToolPreError : ''
                }`}
              >
                {step.output}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
