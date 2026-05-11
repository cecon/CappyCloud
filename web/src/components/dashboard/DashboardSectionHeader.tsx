import styles from './DashboardSectionHeader.module.css'

export interface DashboardSectionHeaderProps {
  /** Texto do título (nível semântico h2). */
  title: string
  /** Subtítulo opcional, uma linha. */
  subtitle?: string
  /** `id` para `aria-labelledby` da seção pai. */
  id?: string
}

/**
 * Cabeçalho padronizado para blocos do dashboard (tipografia e ritmo alinhados).
 */
export function DashboardSectionHeader({ title, subtitle, id }: DashboardSectionHeaderProps) {
  return (
    <header className={styles.root}>
      <h2 id={id} className={styles.title}>
        {title}
      </h2>
      {subtitle ? <p className={styles.sub}>{subtitle}</p> : null}
    </header>
  )
}
