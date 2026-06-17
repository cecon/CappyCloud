import type { CycleMetric } from '../../api'
import styles from './agentic-delivery.module.css'

export function CycleMetricsSummary({ metrics }: { metrics: CycleMetric[] }) {
  return (
    <section className={styles.panel}>
      <div className={styles.panelHeader}>
        <h2>Métricas</h2>
      </div>
      <div className={styles.metricGrid}>
        {metrics.length === 0 ? (
          <p className={styles.muted}>Sem métricas ainda.</p>
        ) : (
          metrics.map((metric) => (
            <div key={metric.metric_name} className={styles.metric}>
              <span>{metric.metric_name}</span>
              <strong>{metric.metric_value ?? metric.metric_text ?? '-'}</strong>
            </div>
          ))
        )}
      </div>
    </section>
  )
}
