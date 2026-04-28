import type { ReactNode } from 'react'
import styles from './MetricStrip.module.css'

export interface MetricCardProps {
  icon: string
  value: string | number
  label: string
  hint: string
  loading?: boolean
}

/**
 * Métrica compacta em linha (ícone, valor, label, delta/status).
 */
export function MetricCard({ icon, value, label, hint, loading }: MetricCardProps) {
  return (
    <div className={styles.metric}>
      <span className={styles.metricIcon} aria-hidden>
        <span className={styles.icon}>{icon}</span>
      </span>
      <div className={styles.metricBody}>
        <span className={styles.metricValue}>{loading ? '…' : value}</span>
        <span className={styles.metricLabel}>{label}</span>
        <span className={styles.metricHint}>{hint}</span>
      </div>
    </div>
  )
}

export interface MetricStripProps {
  children: ReactNode
}

/**
 * Linha horizontal de métricas no dashboard.
 */
export function MetricStrip({ children }: MetricStripProps) {
  return (
    <div className={styles.strip} role="region" aria-label="Métricas do workspace">
      {children}
    </div>
  )
}
