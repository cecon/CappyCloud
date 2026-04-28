import { Link } from 'react-router-dom'
import styles from './HeroCommandPanel.module.css'

export interface HeroCommandPanelProps {
  sessionsCount: number
  readyRepos: number
  activeAgents: number
  activeSkills: number
  loading?: boolean
}

/**
 * Painel principal de boas-vindas com CTAs e visão rápida do workspace.
 */
export function HeroCommandPanel({
  sessionsCount,
  readyRepos,
  activeAgents,
  activeSkills,
  loading,
}: HeroCommandPanelProps) {
  return (
    <section className={styles.hero} aria-labelledby="dashboard-hero-title">
      <div className={styles.copy}>
        <h1 id="dashboard-hero-title" className={styles.title}>
          Controle seus agentes em um só lugar
        </h1>
        <p className={styles.subtitle}>
          Execute sessões isoladas, acompanhe runs, gerencie agentes e prepare repositórios para
          automação segura na nuvem.
        </p>
        <div className={styles.actions}>
          <Link to="/chat" className={styles.primary}>
            <span className={styles.icon}>bolt</span>
            Nova sessão de agente
          </Link>
          <Link to="/agents" className={styles.secondary}>
            <span className={styles.icon}>support_agent</span>
            Gerenciar agentes
          </Link>
          <Link to="/chat" className={styles.tertiary}>
            Ver histórico
            <span className={styles.icon}>chevron_right</span>
          </Link>
        </div>
      </div>
      <div className={styles.overview} aria-label="Visão geral do workspace">
        <div className={styles.overviewHeader}>
          <span className={styles.overviewTitle}>System overview</span>
          <span className={styles.overviewBadge}>Live</span>
        </div>
        <ul className={styles.overviewList}>
          <li>
            <span className={styles.ovIcon} aria-hidden>
              <span className={styles.icon}>chat</span>
            </span>
            <span className={styles.ovLabel}>Sessões</span>
            <span className={styles.ovValue}>{loading ? '…' : sessionsCount}</span>
          </li>
          <li>
            <span className={styles.ovIcon} aria-hidden>
              <span className={styles.icon}>folder_special</span>
            </span>
            <span className={styles.ovLabel}>Repositórios prontos</span>
            <span className={styles.ovValue}>{loading ? '…' : readyRepos}</span>
          </li>
          <li>
            <span className={styles.ovIcon} aria-hidden>
              <span className={styles.icon}>smart_toy</span>
            </span>
            <span className={styles.ovLabel}>Agentes ativos</span>
            <span className={styles.ovValue}>{loading ? '…' : activeAgents}</span>
          </li>
          <li>
            <span className={styles.ovIcon} aria-hidden>
              <span className={styles.icon}>auto_awesome</span>
            </span>
            <span className={styles.ovLabel}>Skills ativas</span>
            <span className={styles.ovValue}>{loading ? '…' : activeSkills}</span>
          </li>
        </ul>
        <p className={styles.overviewFoot}>Todos os subsistemas respondendo.</p>
      </div>
    </section>
  )
}
