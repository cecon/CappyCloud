import { Link } from 'react-router-dom'
import { useCurrentUser } from '../hooks/useCurrentUser'
import styles from './settings.module.css'

type SettingsLink = {
  to: string
  icon: string
  title: string
  description: string
}

const userLinks: SettingsLink[] = [
  {
    to: '/chat',
    icon: 'forum',
    title: 'Chat',
    description: 'Voltar para as conversas e execuções do agente.',
  },
  {
    to: '/skills',
    icon: 'menu_book',
    title: 'Skills',
    description: 'Manter instruções reutilizáveis do agente.',
  },
  {
    to: '/mcp',
    icon: 'lan',
    title: 'MCP Server',
    description: 'Endpoints para ferramentas externas consultarem repositórios.',
  },
]

const adminLinks: SettingsLink[] = [
  {
    to: '/admin',
    icon: 'dashboard',
    title: 'Dashboard admin',
    description: 'Conversas recentes, volume e saúde operacional.',
  },
  {
    to: '/admin/users',
    icon: 'group',
    title: 'Usuários',
    description: 'Papéis e acessos individuais.',
  },
  {
    to: '/admin/repositories',
    icon: 'folder_managed',
    title: 'Repositórios',
    description: 'Catálogo Git usado no chat.',
  },
  {
    to: '/admin/sandboxes',
    icon: 'deployed_code',
    title: 'Sandboxes',
    description: 'Containers e recursos compartilhados.',
  },
]

const superAdminLinks: SettingsLink[] = [
  {
    to: '/admin/skills-global',
    icon: 'library_books',
    title: 'Skills globais',
    description: 'Skills materializadas no boot das sandboxes.',
  },
  {
    to: '/admin/models',
    icon: 'token',
    title: 'Modelos LLM',
    description: 'Ativação global e tier dos modelos.',
  },
  {
    to: '/admin/providers',
    icon: 'hub',
    title: 'Providers LLM',
    description: 'Sincronização e origem do catálogo.',
  },
]

function roleLabel(role: string): string {
  return role === 'admin' ? 'Admin' : 'Usuário'
}

function SettingsLinkRow({ item }: { item: SettingsLink }) {
  return (
    <Link to={item.to} className={styles.settingsLink}>
      <span className={`${styles.icon} ${styles.settingsLinkIcon}`} aria-hidden="true">
        {item.icon}
      </span>
      <span className={styles.settingsLinkContent}>
        <span className={styles.settingsLinkTitle}>{item.title}</span>
        <span className={styles.settingsLinkDesc}>{item.description}</span>
      </span>
      <span className={`${styles.icon} ${styles.settingsLinkArrow}`} aria-hidden="true">
        arrow_forward
      </span>
    </Link>
  )
}

export function SettingsPage() {
  const currentUser = useCurrentUser()
  const isReady = currentUser.status === 'ready'
  const isAdmin = isReady && currentUser.user.role === 'admin'
  const isSuperAdmin = isReady && currentUser.user.is_super_admin

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <div className={styles.headerLinks}>
          <Link to="/chat" className={styles.backLink}>
            <span className={styles.icon}>arrow_back</span>
            Chat
          </Link>
        </div>
        <h1 className={styles.title}>Configurações</h1>
      </header>

      <section className={styles.section}>
        <div className={styles.profileGrid}>
          <div>
            <h2 className={styles.sectionTitle}>Conta</h2>
            <p className={styles.sectionDesc}>Sessão autenticada neste ambiente.</p>
          </div>

          {currentUser.status === 'loading' && (
            <p className={styles.hint}>Carregando conta...</p>
          )}

          {currentUser.status === 'error' && (
            <p className={styles.errorMsg}>{currentUser.message}</p>
          )}

          {currentUser.status === 'anonymous' && (
            <p className={styles.errorMsg}>Sessão não encontrada.</p>
          )}

          {isReady && (
            <div className={styles.identityBlock}>
              <strong>{currentUser.user.email}</strong>
              <div className={styles.rolePills}>
                <span className={styles.badge}>{roleLabel(currentUser.user.role)}</span>
                {isSuperAdmin && <span className={styles.badge_super}>Super admin</span>}
              </div>
            </div>
          )}
        </div>
      </section>

      <section className={styles.section}>
        <h2 className={styles.sectionTitle}>Atalhos</h2>
        <div className={styles.settingsList}>
          {userLinks.map((item) => (
            <SettingsLinkRow key={item.to} item={item} />
          ))}
        </div>
      </section>

      {isAdmin && (
        <section className={styles.section}>
          <h2 className={styles.sectionTitle}>Administração</h2>
          <div className={styles.settingsList}>
            {adminLinks.map((item) => (
              <SettingsLinkRow key={item.to} item={item} />
            ))}
            {isSuperAdmin &&
              superAdminLinks.map((item) => <SettingsLinkRow key={item.to} item={item} />)}
          </div>
        </section>
      )}
    </div>
  )
}
