export type RouteCoverageItem = {
  route: string
  access: 'authenticated' | 'admin' | 'super-admin'
  presentation: 'chat-shell' | 'overlay' | 'account'
}

export const authenticatedRouteCoverage: RouteCoverageItem[] = [
  { route: '/', access: 'authenticated', presentation: 'chat-shell' },
  { route: '/chat', access: 'authenticated', presentation: 'chat-shell' },
  { route: '/runs', access: 'authenticated', presentation: 'overlay' },
  { route: '/agentic-delivery', access: 'authenticated', presentation: 'overlay' },
  { route: '/analytics', access: 'authenticated', presentation: 'overlay' },
  { route: '/skills', access: 'authenticated', presentation: 'overlay' },
  { route: '/mcp', access: 'authenticated', presentation: 'overlay' },
  { route: '/settings', access: 'super-admin', presentation: 'account' },
  { route: '/change-password', access: 'authenticated', presentation: 'account' },
  { route: '/admin/users', access: 'admin', presentation: 'overlay' },
  { route: '/admin/sandboxes', access: 'admin', presentation: 'overlay' },
  { route: '/admin/repositories', access: 'admin', presentation: 'overlay' },
  { route: '/admin/skills-global', access: 'super-admin', presentation: 'overlay' },
  { route: '/admin/models', access: 'admin', presentation: 'overlay' },
  { route: '/admin/providers', access: 'admin', presentation: 'overlay' },
]

export function assertRouteCoverage(routes: string[]) {
  const covered = new Set(authenticatedRouteCoverage.map((item) => item.route))
  return routes.filter((route) => !covered.has(route))
}
