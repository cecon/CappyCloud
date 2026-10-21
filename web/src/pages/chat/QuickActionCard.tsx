import { Link } from 'react-router-dom'
import styles from '../../components/chat.module.css'

/** Renderiza um atalho contextual da tela inicial do agente. */
export function QuickActionCard({ icon, iconColor, title, desc, href, onPick, disabled = false }: {
  icon: string; iconColor: string; title: string; desc: string; href?: string; onPick?: (value: string) => void; disabled?: boolean
}) {
  const content = (
    <div className={styles.quickCard}>
      <div className={styles.quickCardHeader}>
        <span className={styles.icon} style={{ color: iconColor }}>{icon}</span>
        <span className={styles.quickCardTitle}>{title}</span>
      </div>
      <p className={styles.quickCardDesc}>{desc}</p>
    </div>
  )

  if (onPick) {
    return (
      <button
        type="button"
        className={styles.quickCardButton}
        disabled={disabled}
        onClick={() => onPick(desc)}
      >
        {content}
      </button>
    )
  }

  if (!href) return content

  return (
    <Link to={href} className={styles.quickCardLink}>
      {content}
    </Link>
  )
}
