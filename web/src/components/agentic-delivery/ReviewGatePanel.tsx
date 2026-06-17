import type { AgenticReviewGate } from '../../api'
import styles from './agentic-delivery.module.css'

type Props = {
  gates: AgenticReviewGate[]
  onApprove: (gateId: string) => void
}

export function ReviewGatePanel({ gates, onApprove }: Props) {
  return (
    <section className={styles.panel}>
      <div className={styles.panelHeader}>
        <h2>Gates</h2>
      </div>
      <div className={styles.list}>
        {gates.length === 0 ? (
          <p className={styles.muted}>Nenhum gate carregado.</p>
        ) : (
          gates.map((gate) => (
            <div key={gate.id} className={styles.listItem}>
              <span className={styles.badge}>{gate.gate_type}</span>
              <span>{gate.status}</span>
              <button className={styles.iconButton} type="button" onClick={() => onApprove(gate.id)}>
                <span className={styles.icon}>check</span>
              </button>
            </div>
          ))
        )}
      </div>
    </section>
  )
}
