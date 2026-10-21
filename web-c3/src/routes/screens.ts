import type { CurrentUser } from 'data';

/** Nível de acesso de cada tela, igual ao do frontend atual (web/src/App.tsx). */
export type Access = 'user' | 'admin' | 'super';

export interface Screen {
  path: string;
  access: Access;
  /** id do texto em utils/locales/pt.json */
  title: string;
  group: 'main' | 'admin';
}

/** Inventário de specs/013-c3theme-frontend/data-model.md (sem login e troca de senha). */
export const SCREENS: Screen[] = [
  { path: '/chat', access: 'user', title: 'menu.chat', group: 'main' },
  { path: '/skills', access: 'user', title: 'menu.skills', group: 'main' },
  { path: '/mcp', access: 'user', title: 'menu.mcp', group: 'main' },
  { path: '/settings', access: 'super', title: 'menu.settings', group: 'main' },
  { path: '/admin', access: 'admin', title: 'menu.admin', group: 'admin' },
  { path: '/admin/conversations', access: 'admin', title: 'menu.admin.conversations', group: 'admin' },
  { path: '/admin/reports', access: 'admin', title: 'menu.admin.reports', group: 'admin' },
  { path: '/admin/users', access: 'admin', title: 'menu.admin.users', group: 'admin' },
  { path: '/admin/sandboxes', access: 'admin', title: 'menu.admin.sandboxes', group: 'admin' },
  { path: '/admin/models', access: 'admin', title: 'menu.admin.models', group: 'admin' },
  { path: '/admin/providers', access: 'admin', title: 'menu.admin.providers', group: 'admin' },
  { path: '/admin/workspaces', access: 'super', title: 'menu.admin.workspaces', group: 'admin' },
  { path: '/admin/repositories', access: 'super', title: 'menu.admin.repositories', group: 'admin' },
  { path: '/admin/skills-global', access: 'super', title: 'menu.admin.skillsGlobal', group: 'admin' }
];

/** Telas fora do menu (também fora do menu do web/), com rota e regra de acesso próprias. */
export const HIDDEN_SCREENS: Screen[] = [
  { path: '/runs', access: 'user', title: 'menu.runs', group: 'main' },
  { path: '/analytics', access: 'user', title: 'menu.analytics', group: 'main' },
  { path: '/admin/reports/print', access: 'admin', title: 'menu.admin.reports', group: 'admin' }
];

/** Redirecionamentos do frontend atual (contracts/route-map.md, regra 4). */
export const REDIRECTS: Record<string, string> = {
  '/register': '/login',
  '/environments': '/',
  '/admin/agents-global': '/admin/sandboxes'
};

export function canAccess(user: Pick<CurrentUser, 'role' | 'is_super_admin'>, access: Access): boolean {
  if (access === 'super') return user.is_super_admin;
  // Mesma regra de RequireAdmin/RequireSuperAdmin no web/.
  if (access === 'admin') return user.role === 'admin';
  return true;
}
