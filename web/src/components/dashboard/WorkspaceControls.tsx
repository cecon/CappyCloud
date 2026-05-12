import { Link } from 'react-router-dom'
import { StatusBadge, type StatusBadgeVariant } from './StatusBadge'
import styles from './WorkspaceControls.module.css'

export interface WorkspaceControlItem {
  icon: string
  title: string
  text: string
  href?: string
  status: StatusBadgeVariant
}

export interface WorkspaceControlsProps {
  items: WorkspaceControlItem[]
}

/**
 * Lista de roadmap operacional dentro do card (cabeçalho da secção fica no pai).
 */
export function WorkspaceControls({ items }: WorkspaceControlsProps) {
  return (
    <section className={styles.panel} aria-labelledby="workspace-controls-title">
      <ul className={styles.list}>
        {items.map((item) => (
          <li key={item.title}>
            {item.href ? (
              <Link to={item.href} className={styles.link}>
                <ControlRow {...item} />
              </Link>
            ) : (
              <div className={styles.static}>
                <ControlRow {...item} />
              </div>
            )}
          </li>
        ))}
      </ul>
    </section>
  )
}

function ControlRow({ icon, title, text, status }: WorkspaceControlItem) {
  return (
    <div className={styles.row}>
      <span className={styles.iconWrap} aria-hidden>
        <span className={styles.icon}>{icon}</span>
      </span>
      <div className={styles.body}>
        <div className={styles.titleRow}>
          <strong className={styles.itemTitle}>{title}</strong>
          <StatusBadge variant={status} />
        </div>
        <p className={styles.text}>{text}</p>
      </div>
    </div>
  )
}
