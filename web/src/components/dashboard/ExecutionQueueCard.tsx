import { DashboardSectionHeader } from './DashboardSectionHeader'
import styles from './ExecutionQueueCard.module.css'

/**
 * Resumo operacional / fila de execução (dados ilustrativos para densidade do dashboard).
 */
export function ExecutionQueueCard() {
  return (
    <section className={styles.panel} aria-labelledby="execution-queue-title">
      <DashboardSectionHeader
        id="execution-queue-title"
        title="Fila de execução"
        subtitle="Resumo operacional do runtime."
      />

      <div className={styles.stats}>
        <div className={styles.stat}>
          <span className={styles.statLabel}>Pendentes</span>
          <span className={styles.statValue}>0</span>
        </div>
        <div className={styles.stat}>
          <span className={styles.statLabel}>Em execução</span>
          <span className={styles.statValue}>1</span>
        </div>
        <div className={styles.stat}>
          <span className={styles.statLabel}>Falhas recentes</span>
          <span className={styles.statValue}>0</span>
        </div>
        <div className={styles.stat}>
          <span className={styles.statLabel}>Tempo médio</span>
          <span className={styles.statValue}>1s</span>
        </div>
      </div>

      <p className={styles.listLabel}>Últimas tarefas</p>
      <ul className={styles.queueList}>
        <li className={styles.queueItem}>
          <span className={styles.queueName}>AutoSystem analysis</span>
          <span className={`${styles.queueStatus} ${styles.done}`}>Concluído</span>
        </li>
        <li className={styles.queueItem}>
          <span className={styles.queueName}>Context sync</span>
          <span className={`${styles.queueStatus} ${styles.done}`}>Concluído</span>
        </li>
        <li className={styles.queueItem}>
          <span className={styles.queueName}>MCP check</span>
          <span className={`${styles.queueStatus} ${styles.wait}`}>Aguardando</span>
        </li>
      </ul>
    </section>
  )
}
