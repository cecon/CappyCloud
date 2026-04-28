import type { ReactNode } from 'react'
import styles from './DashboardShell.module.css'

export interface DashboardShellProps {
  children: ReactNode
}

/**
 * Container da página do dashboard: fundo, largura máxima e padding.
 */
export function DashboardShell({ children }: DashboardShellProps) {
  return <div className={styles.shell}>{children}</div>
}
