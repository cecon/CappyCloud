import styles from '../../components/chat.module.css'

/* ────────────────────────────────────────────────────────────────
   Message bubble
   ──────────────────────────────────────────────────────────────── */
export function AgentBubble({
  children,
  compact = false,
}: {
  children: React.ReactNode
  compact?: boolean
}) {
  return (
    <div className={`${styles.agentBubble} ${compact ? styles.agentBubbleCompact : ''}`}>
      <div className={styles.agentBubbleAvatar}>
        <img src="/capybara.png" alt="" />
      </div>
      <div className={styles.agentBubbleBody}>{children}</div>
    </div>
  )
}
