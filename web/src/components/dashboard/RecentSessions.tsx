import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import type { Conversation } from '../../api'
import { StatusBadge, type StatusBadgeVariant } from './StatusBadge'
import styles from './RecentSessions.module.css'

export type SessionFilter = 'all' | 'completed' | 'running'

export interface RecentSessionsProps {
  conversations: Conversation[]
  loading: boolean
  agentLabel: (agentId: string | null | undefined) => string
  statusFor: (conversation: Conversation) => StatusBadgeVariant
  formatDuration: (conversation: Conversation) => string
  formatDateTime: (iso: string) => string
  className?: string
}

/**
 * Lista refinada de sessões recentes com hierarquia, filtros e truncamento.
 */
export function RecentSessions({
  conversations,
  loading,
  agentLabel,
  statusFor,
  formatDuration,
  formatDateTime,
  className,
}: RecentSessionsProps) {
  const [filter, setFilter] = useState<SessionFilter>('all')

  const filtered = useMemo(() => {
    if (filter === 'all') return conversations
    return conversations.filter((c) => {
      const s = statusFor(c)
      if (filter === 'completed') return s === 'completed'
      return s === 'running'
    })
  }, [conversations, filter, statusFor])

  const panelClass = [styles.panel, className].filter(Boolean).join(' ')

  return (
    <section className={panelClass} aria-labelledby="recent-sessions-title">
      <div className={styles.toolbar}>
        <div className={styles.toolbarMain}>
          <h2 id="recent-sessions-title" className={styles.title}>
            Sessões recentes
          </h2>
          <p className={styles.sub}>Retome o contexto com um clique.</p>
        </div>
        <div className={styles.toolbarActions}>
          <div className={styles.filters} role="group" aria-label="Filtrar sessões">
            {(
              [
                ['all', 'Todas'],
                ['completed', 'Concluídas'],
                ['running', 'Em execução'],
              ] as const
            ).map(([key, label]) => (
              <button
                key={key}
                type="button"
                className={`${styles.filterBtn} ${filter === key ? styles.filterBtnActive : ''}`}
                onClick={() => setFilter(key)}
                disabled={loading}
              >
                {label}
              </button>
            ))}
          </div>
          <Link to="/chat" className={styles.link}>
            Ver chat
          </Link>
        </div>
      </div>
      {loading ? (
        <p className={styles.muted}>Carregando sessões…</p>
      ) : filtered.length > 0 ? (
        <ul className={styles.list}>
          {filtered.map((conversation, index) => (
            <li key={conversation.id} className={styles.itemWrap}>
              <Link to="/chat" className={styles.item}>
                <span className={styles.itemIcon} aria-hidden>
                  <span className={styles.icon}>
                    {statusFor(conversation) === 'running' ? 'progress_activity' : 'chat_bubble'}
                  </span>
                </span>
                <div className={styles.itemMain}>
                  <span className={styles.itemTitle} title={conversation.title}>
                    {conversation.title}
                  </span>
                  <div className={styles.itemMeta}>
                    <span className={styles.metaTruncate} title={agentLabel(conversation.agent_id)}>
                      {agentLabel(conversation.agent_id)}
                    </span>
                    <span className={styles.metaSep} aria-hidden>
                      ·
                    </span>
                    <span className={styles.metaNoShrink}>{formatDateTime(conversation.updated_at)}</span>
                    <span className={styles.metaSep} aria-hidden>
                      ·
                    </span>
                    <span className={styles.metaNoShrink}>{formatDuration(conversation)}</span>
                  </div>
                </div>
                <div className={styles.badgeCell}>
                  <StatusBadge variant={statusFor(conversation)} />
                </div>
                <span className={styles.open}>
                  Abrir
                  <span className={styles.icon}>chevron_right</span>
                </span>
              </Link>
              {index < filtered.length - 1 ? <div className={styles.divider} aria-hidden /> : null}
            </li>
          ))}
        </ul>
      ) : conversations.length > 0 ? (
        <p className={styles.muted}>Nenhuma sessão neste filtro.</p>
      ) : (
        <p className={styles.muted}>Nenhuma conversa ainda. Inicie uma nova sessão.</p>
      )}
    </section>
  )
}
