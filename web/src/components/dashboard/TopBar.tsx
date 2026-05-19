import { Link } from 'react-router-dom'
import { useCurrentUser } from '../../hooks/useCurrentUser'
import styles from './TopBar.module.css'

/**
 * Barra superior compacta: marca, contexto e ações globais.
 */
export function TopBar() {
  const currentUser = useCurrentUser()
  const isSuperAdmin = currentUser.status === 'ready' && currentUser.user.is_super_admin

  return (
    <header className={styles.bar}>
      <div className={styles.left}>
        <Link to="/" className={styles.brand} aria-label="CappyCloud — início">
          <img src="/capybara.png" alt="" className={styles.logo} width={32} height={32} />
          <span className={styles.brandName}>CappyCloud</span>
        </Link>
        <span className={styles.sep} aria-hidden>
          /
        </span>
        <span className={styles.crumb}>Command Center</span>
      </div>
      <div className={styles.hubArt} aria-hidden>
        <img
          src="/command-center-hub.svg"
          alt=""
          className={styles.hubImg}
          width={440}
          height={80}
          decoding="async"
        />
      </div>
      <div className={styles.right}>
        <div className={styles.statusPill} title="Runtime do workspace">
          <span className={styles.statusDot} aria-hidden />
          <span>Online</span>
        </div>
        <Link to="/chat" className={styles.primaryBtn}>
          <span className={styles.icon}>add</span>
          Nova sessão
        </Link>
        {isSuperAdmin && (
          <Link
            to="/settings"
            className={styles.avatar}
            title="Configurações"
            aria-label="Configurações"
          >
            <span className={styles.avatarInner}>CC</span>
          </Link>
        )}
      </div>
    </header>
  )
}
