import { describe, expect, it } from 'vitest'
import { roleFromUser, visibleNavigationItems } from './navigation'

const adminRoutes = (role: ReturnType<typeof roleFromUser>) =>
  visibleNavigationItems(role, 'admin').map((item) => item.to)

describe('admin de workspace na navegação', () => {
  it('reconhece o papel pelo admin_workspace_ids', () => {
    expect(roleFromUser({ role: 'user', admin_workspace_ids: ['ws-1'] })).toBe('workspace-admin')
    expect(roleFromUser({ role: 'user', admin_workspace_ids: [] })).toBe('user')
    expect(roleFromUser({ role: 'admin', admin_workspace_ids: ['ws-1'] })).toBe('admin')
  })

  it('mostra só as telas que o admin de workspace pode usar', () => {
    expect(adminRoutes('workspace-admin')).toEqual([
      '/admin',
      '/admin/conversations',
      '/admin/reports',
      '/admin/users',
      '/admin/workspaces',
    ])
    expect(adminRoutes('user')).toEqual([])
    expect(adminRoutes('admin')).not.toContain('/admin/workspaces')
  })
})
