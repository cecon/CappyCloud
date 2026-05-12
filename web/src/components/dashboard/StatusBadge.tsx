import styles from './StatusBadge.module.css'

export type StatusBadgeVariant =
  | 'planned'
  | 'development'
  | 'available'
  | 'beta'
  | 'completed'
  | 'running'
  | 'paused'
  | 'error'

const LABELS: Record<StatusBadgeVariant, string> = {
  planned: 'Planejado',
  development: 'Em desenvolvimento',
  available: 'Disponível',
  beta: 'Beta',
  completed: 'Concluída',
  running: 'Em execução',
  paused: 'Pausada',
  error: 'Erro',
}

export interface StatusBadgeProps {
  /** Variante semântica do badge. */
  variant: StatusBadgeVariant
  /** Sobrescreve o texto padrão da variante. */
  label?: string
  className?: string
}

/**
 * Badge de status para roadmap, sessões e estados operacionais.
 */
export function StatusBadge({ variant, label, className }: StatusBadgeProps) {
  const text = label ?? LABELS[variant]
  return (
    <span className={`${styles.badge} ${styles[variant]} ${className ?? ''}`.trim()}>{text}</span>
  )
}
