import type { AgenticOutput } from '../../api'
import styles from './agentic-delivery.module.css'

export function AgentOutputReviewList({ outputs }: { outputs: AgenticOutput[] }) {
  return (
    <section className={styles.panel}>
      <div className={styles.panelHeader}>
        <h2>Outputs</h2>
      </div>
      <div className={styles.list}>
        {outputs.length === 0 ? (
          <p className={styles.muted}>Sem outputs do agente ainda.</p>
        ) : (
          outputs.map((output) => (
            <article key={output.id} className={styles.outputItem}>
              <div className={styles.statusRow}>
                <strong>{output.title}</strong>
                <span className={styles.badge}>{output.validation_status}</span>
              </div>
              <p className={styles.muted}>{output.output_type}</p>
              <div className={styles.chips}>
                {output.evidence_links.map((link) => (
                  <span key={`${output.id}-${link.claim_summary}`} className={styles.chip}>
                    {link.support_status}
                  </span>
                ))}
              </div>
            </article>
          ))
        )}
      </div>
    </section>
  )
}
