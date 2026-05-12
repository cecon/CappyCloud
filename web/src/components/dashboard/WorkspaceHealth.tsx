import { DashboardSectionHeader } from './DashboardSectionHeader'
import styles from './WorkspaceHealth.module.css'

export interface WorkspaceHealthProps {
  /** Texto para última execução (ex.: "há 12 min"). */
  lastRunLabel: string
  /** Indica se há sandbox utilizável. */
  sandboxActive: boolean
  /** Número exibido para integrações MCP (placeholder operacional). */
  mcpConnected?: number
}

/**
 * Painel lateral de saúde e fila do workspace.
 */
export function WorkspaceHealth({
  lastRunLabel,
  sandboxActive,
  mcpConnected = 2,
}: WorkspaceHealthProps) {
  return (
    <section className={styles.panel} aria-labelledby="workspace-health-title">
      <DashboardSectionHeader
        id="workspace-health-title"
        title="Saúde do workspace"
        subtitle="Runtime, fila e conectores."
      />
      <dl className={styles.list}>
        <div className={styles.row}>
          <dt>Runtime</dt>
          <dd>
            <span className={styles.okDot} aria-hidden />
            Online
          </dd>
        </div>
        <div className={styles.row}>
          <dt>Fila</dt>
          <dd>0 pendentes</dd>
        </div>
        <div className={styles.row}>
          <dt>Última execução</dt>
          <dd>{lastRunLabel}</dd>
        </div>
        <div className={styles.row}>
          <dt>Sandbox</dt>
          <dd>{sandboxActive ? 'Ativo' : 'Indisponível'}</dd>
        </div>
        <div className={styles.row}>
          <dt>MCP</dt>
          <dd>{mcpConnected} conectados</dd>
        </div>
      </dl>
    </section>
  )
}
