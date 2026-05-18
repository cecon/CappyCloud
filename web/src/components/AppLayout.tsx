import { useEffect, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { setToken } from '../api'
import { useCurrentUser } from '../hooks/useCurrentUser'
import styles from './app-layout.module.css'

type AppLayoutProps = {
  children: React.ReactNode
}

type NavItem = {
  to: string
  icon: string
  label: string
}

type NavGroup = {
  id: string
  label: string
  items: NavItem[]
  /** Quando ``false``, o grupo nunca colapsa (útil para grupos curtos). */
  collapsible?: boolean
  /** Quando ``true``, o grupo só é renderizado para utilizadores ADMIN. */
  adminOnly?: boolean
}

const NAV_GROUPS: NavGroup[] = [
  {
    id: 'operacao',
    label: 'Operação',
    items: [
      { to: '/', icon: 'dashboard', label: 'Dashboard' },
      { to: '/chat', icon: 'chat_bubble', label: 'Chat' },
      { to: '/runs', icon: 'history', label: 'Runs' },
      { to: '/analytics', icon: 'analytics', label: 'Analytics' },
    ],
  },
  {
    id: 'cadastros',
    label: 'Cadastros',
    adminOnly: true,
    items: [
      { to: '/admin/users', icon: 'group', label: 'Usuários' },
      { to: '/admin/sandboxes', icon: 'dns', label: 'Sandboxes' },
      { to: '/admin/repositories', icon: 'folder_managed', label: 'Repositórios' },
      { to: '/skills', icon: 'menu_book', label: 'Skills (por repo)' },
      { to: '/admin/models', icon: 'token', label: 'Modelos LLM' },
      { to: '/admin/providers', icon: 'cloud', label: 'Providers LLM' },
    ],
  },
  {
    id: 'sistema',
    label: 'Sistema',
    items: [{ to: '/settings', icon: 'settings', label: 'Configurações' }],
  },
]

const PAGE_TITLES: Record<string, { title: string; subtitle: string }> = {
  '/': { title: 'Dashboard', subtitle: 'Visão operacional do CappyCloud' },
  '/chat': { title: 'Chat', subtitle: 'Agente com worktree isolado e contexto do projeto' },
  '/runs': { title: 'Runs', subtitle: 'Execuções, eventos e estado das sessões' },
  '/analytics': { title: 'Analytics', subtitle: 'Uso, custo e saúde operacional' },
  '/skills': { title: 'Skills (por repo)', subtitle: 'Regras curtas vinculadas a repositórios' },
  '/mcp': { title: 'MCPs', subtitle: 'Servidores MCP carregados pelo sandbox' },
  '/settings': {
    title: 'Configurações',
    subtitle: 'Provedores, modelos e preferências da plataforma',
  },
  '/admin/users': { title: 'Usuários', subtitle: 'Cadastro de utilizadores e papéis' },
  '/admin/sandboxes': {
    title: 'Sandboxes',
    subtitle: 'Containers openclaude por cliente/squad',
  },
  '/admin/repositories': {
    title: 'Repositórios',
    subtitle: 'Catálogo Git, credenciais e branches default',
  },
  '/admin/skills-global': {
    title: 'Skills globais',
    subtitle: 'Skills materializadas em todos os worktrees do sandbox',
  },
  '/admin/agents-global': {
    title: 'Subagents globais',
    subtitle: 'Agents materializados no ~/.claude/agents do sandbox',
  },
  '/admin/models': { title: 'Modelos LLM', subtitle: 'Catálogo sincronizado do provider' },
  '/admin/providers': { title: 'Providers LLM', subtitle: 'OpenRouter, Azure AI Foundry, ...' },
}

const APP_NAV_COLLAPSED_KEY = 'cappycloud.layout.navCollapsed'
const GROUP_COLLAPSED_KEY = 'cappycloud.layout.groupsCollapsed'

function readCollapsedGroups(): Record<string, boolean> {
  try {
    const raw = window.localStorage.getItem(GROUP_COLLAPSED_KEY)
    if (!raw) return {}
    const parsed = JSON.parse(raw) as unknown
    if (parsed && typeof parsed === 'object') {
      return parsed as Record<string, boolean>
    }
  } catch {
    // Preferência local não deve bloquear navegação.
  }
  return {}
}

export function AppLayout({ children }: AppLayoutProps) {
  const { pathname } = useLocation()
  const meta = PAGE_TITLES[pathname] ?? PAGE_TITLES['/']
  const currentUserState = useCurrentUser()
  const isAdmin =
    currentUserState.status === 'ready' && currentUserState.user.role === 'admin'
  const visibleGroups = NAV_GROUPS.filter((g) => !g.adminOnly || isAdmin)
  const [navCollapsed, setNavCollapsed] = useState(() => {
    try {
      return window.localStorage.getItem(APP_NAV_COLLAPSED_KEY) === 'true'
    } catch {
      return false
    }
  })
  const [collapsedGroups, setCollapsedGroups] =
    useState<Record<string, boolean>>(readCollapsedGroups)
  const navToggleIcon = navCollapsed ? 'keyboard_double_arrow_right' : 'keyboard_double_arrow_left'

  useEffect(() => {
    try {
      window.localStorage.setItem(APP_NAV_COLLAPSED_KEY, String(navCollapsed))
    } catch {
      // Preferência visual local não deve bloquear navegação.
    }
  }, [navCollapsed])

  useEffect(() => {
    try {
      window.localStorage.setItem(GROUP_COLLAPSED_KEY, JSON.stringify(collapsedGroups))
    } catch {
      // ignore
    }
  }, [collapsedGroups])

  function toggleGroup(id: string) {
    setCollapsedGroups((prev) => ({ ...prev, [id]: !prev[id] }))
  }

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
          {visibleGroups.map((group) => {
            const isCollapsible = group.collapsible !== false && group.items.length > 1
            const isCollapsed = isCollapsible && collapsedGroups[group.id] === true
            const hasActive = group.items.some((it) => it.to === pathname)
            const showItems = !isCollapsed || hasActive
            return (
              <div key={group.id} className={styles.navGroup}>
                {isCollapsible ? (
                  <button
                    type="button"
                    className={styles.navGroupHeader}
                    onClick={() => toggleGroup(group.id)}
                    aria-expanded={!isCollapsed}
                    aria-controls={`navgroup-${group.id}`}
                  >
                    <span className={styles.navGroupLabel}>{group.label}</span>
                    <span
                      className={`${styles.icon} ${styles.navGroupChevron} ${
                        isCollapsed ? styles.navGroupChevronCollapsed : ''
                      }`}
                    >
                      expand_more
                    </span>
                  </button>
                ) : (
                  <div className={styles.navGroupHeaderStatic}>
                    <span className={styles.navGroupLabel}>{group.label}</span>
                  </div>
                )}

                {showItems && (
                  <div id={`navgroup-${group.id}`} className={styles.navGroupItems}>
                    {group.items.map((item) => {
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
                        </Link>
                      )
                    })}
                  </div>
                )}
              </div>
            )
          })}
        </nav>

        <div className={styles.profile}>
          <button type="button" className={styles.profileButton} title="Perfil do usuário">
            <span className={styles.avatar}>
              {currentUserState.status === 'ready'
                ? currentUserState.user.email.slice(0, 2).toUpperCase()
                : 'EM'}
            </span>
            <span className={styles.profileText}>
              <span className={styles.profileName}>
                {currentUserState.status === 'ready'
                  ? currentUserState.user.email
                  : 'Usuário'}
              </span>
              <span className={styles.profileMeta}>
                {currentUserState.status === 'ready'
                  ? currentUserState.user.role === 'admin'
                    ? 'Administrador'
                    : 'Utilizador'
                  : 'Perfil e preferências'}
              </span>
            </span>
          </button>
          <button
            type="button"
            className={styles.logoutButton}
            onClick={logout}
            title="Sair"
          >
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
            <Link
              to="/settings"
              className={styles.iconButton}
              title="Configurações"
              aria-label="Configurações"
            >
              <span className={styles.icon}>settings</span>
            </Link>
          </div>
        </header>

        <main className={styles.content}>{children}</main>
      </div>
    </div>
  )
}
