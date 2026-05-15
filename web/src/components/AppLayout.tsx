import { useEffect, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { setToken } from '../api'
import styles from './app-layout.module.css'

type AppLayoutProps = {
  children: React.ReactNode
}

const NAV_ITEMS = [
  { to: '/', icon: 'dashboard', label: 'Dashboard', section: 'Visão geral' },
  { to: '/chat', icon: 'chat_bubble', label: 'Chat', section: 'Agente' },
  { to: '/runs', icon: 'history', label: 'Runs', section: 'Operação' },
  { to: '/analytics', icon: 'analytics', label: 'Analytics', section: 'Operação' },
  { to: '/skills', icon: 'menu_book', label: 'Skills', section: 'Configuração' },
  { to: '/mcp', icon: 'extension', label: 'MCP', section: 'Configuração' },
  { to: '/settings', icon: 'settings', label: 'Configurações', section: 'Admin' },
]

const PAGE_TITLES: Record<string, { title: string; subtitle: string }> = {
  '/': { title: 'Dashboard', subtitle: 'Visão operacional do CappyCloud' },
  '/chat': { title: 'Chat', subtitle: 'Agente com worktree isolado e contexto do projeto' },
  '/runs': { title: 'Runs', subtitle: 'Execuções, eventos e estado das sessões' },
  '/analytics': { title: 'Analytics', subtitle: 'Uso, custo e saúde operacional' },
  '/skills': { title: 'Skills', subtitle: 'Regras curtas por repositório para o agente' },
  '/mcp': { title: 'MCP', subtitle: 'Ferramentas externas conectadas ao sandbox' },
  '/settings': { title: 'Configurações', subtitle: 'Provedores, modelos e preferências da plataforma' },
}

const APP_NAV_COLLAPSED_KEY = 'cappycloud.layout.navCollapsed'

export function AppLayout({ children }: AppLayoutProps) {
  const { pathname } = useLocation()
  const meta = PAGE_TITLES[pathname] ?? PAGE_TITLES['/']
  const [navCollapsed, setNavCollapsed] = useState(() => {
    try {
      return window.localStorage.getItem(APP_NAV_COLLAPSED_KEY) === 'true'
    } catch {
      return false
    }
  })
  const navToggleIcon = navCollapsed ? 'keyboard_double_arrow_right' : 'keyboard_double_arrow_left'

  useEffect(() => {
    try {
      window.localStorage.setItem(APP_NAV_COLLAPSED_KEY, String(navCollapsed))
    } catch {
      // Preferência visual local não deve bloquear navegação.
    }
  }, [navCollapsed])

  function logout() {
    setToken(null)
    window.location.href = '/login'
  }

  return (
    <div className={`${styles.shell} ${navCollapsed ? styles.shellCollapsed : ''}`}>
      <aside className={styles.sidebar} aria-label="Navegação principal">
        <div className={styles.brand}>
          <img src="/capybara.png" alt="" className={styles.logo} />
          <div>
            <div className={styles.brandName}>CappyCloud</div>
            <div className={styles.brandMeta}>Admin Console</div>
          </div>
          <button
            type="button"
            className={styles.collapseButton}
            onClick={() => setNavCollapsed((prev) => !prev)}
            title={navCollapsed ? 'Expandir navegação' : 'Recolher navegação'}
            aria-label={navCollapsed ? 'Expandir navegação' : 'Recolher navegação'}
          >
            <span className={styles.icon}>{navToggleIcon}</span>
          </button>
        </div>

        <nav className={styles.nav}>
          {NAV_ITEMS.map((item) => {
            const active = pathname === item.to
            return (
              <Link
                key={item.to}
                to={item.to}
                className={`${styles.navItem} ${active ? styles.navItemActive : ''}`}
                aria-current={active ? 'page' : undefined}
                aria-label={item.label}
                title={item.label}
              >
                <span className={styles.icon}>{item.icon}</span>
                <span className={styles.navLabel}>{item.label}</span>
                <span className={styles.navSection}>{item.section}</span>
              </Link>
            )
          })}
        </nav>

        <div className={styles.profile}>
          <button type="button" className={styles.profileButton} title="Perfil do usuário">
            <span className={styles.avatar}>EM</span>
            <span className={styles.profileText}>
              <span className={styles.profileName}>Usuário</span>
              <span className={styles.profileMeta}>Perfil e preferências</span>
            </span>
          </button>
          <button type="button" className={styles.logoutButton} onClick={logout} title="Sair">
            <span className={styles.icon}>logout</span>
          </button>
        </div>
      </aside>

      <div className={styles.workspace}>
        <header className={styles.header}>
          <div>
            <h1 className={styles.title}>{meta.title}</h1>
            <p className={styles.subtitle}>{meta.subtitle}</p>
          </div>
          <div className={styles.headerActions}>
            <button
              type="button"
              className={styles.iconButton}
              onClick={() => setNavCollapsed((prev) => !prev)}
              title={navCollapsed ? 'Expandir menu principal' : 'Recolher menu principal'}
              aria-label={navCollapsed ? 'Expandir menu principal' : 'Recolher menu principal'}
            >
              <span className={styles.icon}>{navToggleIcon}</span>
            </button>
            <Link to="/skills" className={styles.headerLink}>
              <span className={styles.icon}>menu_book</span>
              Skills
            </Link>
            <Link to="/settings" className={styles.iconButton} title="Configurações" aria-label="Configurações">
              <span className={styles.icon}>settings</span>
            </Link>
          </div>
        </header>

        <main className={styles.content}>
          {children}
        </main>
      </div>
    </div>
  )
}
