import type { AgenticCycleStatus } from '../../api'
import styles from './agentic-delivery.module.css'

export function CycleLifecycleBadge({ status }: { status: AgenticCycleStatus | null }) {
  return <span className={styles.lifecycleBadge}>{status ?? 'Draft'}</span>
}
