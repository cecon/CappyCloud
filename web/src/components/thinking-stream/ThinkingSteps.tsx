import styles from '../chat.module.css'
import { displayToolName, formatElapsed, summarizeToolInput } from './labels'
import type { ThoughtStep } from './types'

/** Linha discreta de fase: workspace/contexto/modelo com a duração real. */
export function ThinkingPhaseStep({ step }: { step: Extract<ThoughtStep, { kind: 'phase' }> }) {
  const mark = step.isError ? '✗' : step.done ? '✓' : '⟳'
  return (
    <div
      className={`${styles.thinkingStreamPhaseStep} ${
        step.done ? '' : styles.thinkingStreamPhaseStepRunning
      } ${step.isError ? styles.thinkingStreamPhaseStepError : ''}`}
    >
      <span className={styles.thinkingStreamPhaseMark} aria-hidden="true">
        {mark}
      </span>
      <span className={styles.thinkingStreamPhaseLabel}>{step.label}</span>
      {step.done && step.durationMs !== undefined && (
        <span className={styles.thinkingStreamPhaseDuration}>{formatElapsed(step.durationMs)}</span>
      )}
    </div>
  )
}

export function ThinkingTextStep({ content }: { content: string }) {
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

export function ThinkingToolStep({
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
          {step.isError ? '✗' : step.done ? '▸' : '⟳'}
        </span>
        <span className={styles.thinkingStreamToolName}>{displayToolName(step.name, step.input)}</span>
        <span className={styles.thinkingStreamToolSummary}>{summary}</span>
        <span className={styles.thinkingStreamToolChevron} aria-hidden="true">
          {expanded ? '−' : '+'}
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
                {step.isError ? 'Saída (erro)' : 'Saída'}
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
