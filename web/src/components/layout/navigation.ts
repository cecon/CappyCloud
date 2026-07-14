import type { CappyIconName } from './icons'

export type CappyRole = 'user' | 'admin' | 'super-admin'

export type NavigationItem = {
  to: string
  label: string
  description: string
  icon: CappyIconName
  section: 'primary' | 'work' | 'admin' | 'account'
  adminOnly?: boolean
  superAdminOnly?: boolean
  overlay?: boolean
}

export const routeTitles: Record<string, { title: string; subtitle: string }> = {
  '/': { title: 'Chat', subtitle: 'Conversa, contexto e agente no centro' },
  '/chat': { title: 'Chat', subtitle: 'Agente com workspace, permissao e modelo em contexto' },
  '/runs': { title: 'Runs', subtitle: 'Historico de execucoes e eventos das sessoes' },
  '/analytics': { title: 'Analytics', subtitle: 'Uso, custo e saude operacional' },
  '/skills': { title: 'Skills por repositorio', subtitle: 'Regras curtas vinculadas aos repositorios' },
  '/mcp': { title: 'MCP Server', subtitle: 'Acesso externo controlado aos repositorios' },
  '/settings': { title: 'Configuracoes', subtitle: 'Preferencias e atalhos do ambiente' },
  '/change-password': { title: 'Alterar senha', subtitle: 'Superficie de conta alinhada ao novo tema' },
  '/admin/users': { title: 'Usuarios', subtitle: 'Cadastro de utilizadores, papeis e permissoes' },
  '/admin/sandboxes': { title: 'Sandboxes', subtitle: 'Containers por cliente, squad e repositorio' },
  '/admin/repositories': { title: 'Repositorios', subtitle: 'Catalogo Git, credenciais e branches default' },
  '/admin/skills-global': { title: 'Skills globais', subtitle: 'Skills materializadas em todos os worktrees' },
  '/admin/models': { title: 'Modelos LLM', subtitle: 'Catalogo sincronizado do provider' },
  '/admin/providers': { title: 'Providers LLM', subtitle: 'OpenRouter, Azure AI Foundry e outros' },
}

export const navigationItems: NavigationItem[] = [
  {
    to: '/chat',
    label: 'Nova conversa',
    description: 'Abrir o chat principal',
    icon: 'newChat',
    section: 'primary',
  },
  { to: '/skills', label: 'Skills', description: 'Skills por repositorio', icon: 'skills', section: 'work', overlay: true },
  { to: '/mcp', label: 'MCP Server', description: 'Servidores MCP', icon: 'mcp', section: 'work', overlay: true },
  { to: '/settings', label: 'Configuracoes', description: 'Preferencias', icon: 'settings', section: 'account', superAdminOnly: true },
  { to: '/change-password', label: 'Alterar senha', description: 'Conta e acesso', icon: 'changePassword', section: 'account' },
  { to: '/admin/users', label: 'Usuarios', description: 'Papeis e acesso', icon: 'users', section: 'admin', adminOnly: true, overlay: true },
  { to: '/admin/sandboxes', label: 'Sandboxes', description: 'Ambientes isolados', icon: 'sandboxes', section: 'admin', adminOnly: true, overlay: true },
  { to: '/admin/repositories', label: 'Repositorios', description: 'Catalogo Git', icon: 'repositories', section: 'admin', adminOnly: true, overlay: true },
  {
    to: '/admin/skills-global',
    label: 'Skills globais',
    description: 'Skills globais',
    icon: 'library',
    section: 'admin',
    superAdminOnly: true,
    overlay: true,
  },
  { to: '/admin/models', label: 'Modelos LLM', description: 'Catalogo de modelos', icon: 'models', section: 'admin', adminOnly: true, overlay: true },
  { to: '/admin/providers', label: 'Providers LLM', description: 'Credenciais e providers', icon: 'providers', section: 'admin', adminOnly: true, overlay: true },
]

export function roleFromUser(user: { role: string; is_super_admin?: boolean } | null): CappyRole {
  if (user?.is_super_admin) return 'super-admin'
  if (user?.role === 'admin') return 'admin'
  return 'user'
}

export function canAccessNavigationItem(item: NavigationItem, role: CappyRole): boolean {
  if (item.superAdminOnly) return role === 'super-admin'
  if (item.adminOnly) return role === 'admin' || role === 'super-admin'
  return true
}

export function visibleNavigationItems(role: CappyRole, section?: NavigationItem['section']) {
  return navigationItems.filter(
    (item) => canAccessNavigationItem(item, role) && (!section || item.section === section),
  )
}

export function isAdminRoute(pathname: string) {
  return pathname.startsWith('/admin/')
}
