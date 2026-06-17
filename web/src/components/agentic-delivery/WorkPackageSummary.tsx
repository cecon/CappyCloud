import type { AgenticCycleCreated, AgenticPrepareResponse } from '../../api'
import styles from './agentic-delivery.module.css'

type Props = {
  cycle: AgenticCycleCreated | null
  prepared: AgenticPrepareResponse | null
  onRun: () => void
  disabled?: boolean
}

export function WorkPackageSummary({ cycle, prepared, onRun, disabled }: Props) {
  return (
    <section className={styles.panel}>
      <div className={styles.panelHeader}>
        <h2>Pacote</h2>
        <button className={styles.secondaryButton} disabled={!prepared || disabled} onClick={onRun} type="button">
          <span className={styles.icon}>play_arrow</span>
          Executar
        </button>
      </div>

      {!cycle ? (
        <p className={styles.muted}>Nenhum ciclo criado nesta sessão.</p>
      ) : (
        <div className={styles.stack}>
          <div className={styles.statusRow}>
            <span className={styles.badge}>{prepared?.status ?? cycle.status}</span>
            <span className={styles.muted}>{cycle.id}</span>
          </div>
          <div>
            <span className={styles.label}>Gates obrigatórios</span>
            <div className={styles.chips}>
              {(prepared?.required_gates ?? cycle.required_gates).map((gate) => (
                <span key={gate} className={styles.chip}>
                  {gate}
                </span>
              ))}
            </div>
          </div>
          {prepared?.missing_inputs.length ? (
            <p className={styles.error}>Campos pendentes: {prepared.missing_inputs.join(', ')}</p>
          ) : null}
        </div>
      )}
    </section>
  )
}
