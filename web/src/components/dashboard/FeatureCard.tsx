import { Link } from 'react-router-dom'
import styles from './FeatureCard.module.css'

export interface FeatureCardProps {
  icon: string
  title: string
  description: string
  href: string
  cta: string
}

/**
 * Card de atalho para uma área do produto (ícone, título, descrição, CTA).
 */
export function FeatureCard({ icon, title, description, href, cta }: FeatureCardProps) {
  return (
    <Link to={href} className={styles.card}>
      <span className={styles.iconWrap} aria-hidden>
        <span className={styles.icon}>{icon}</span>
      </span>
      <span className={styles.title}>{title}</span>
      <span className={styles.description}>{description}</span>
      <span className={styles.cta}>
        {cta}
        <span className={styles.icon}>arrow_forward</span>
      </span>
    </Link>
  )
}
