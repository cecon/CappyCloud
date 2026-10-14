import type { AdminWorkspace, WorkspaceRepositoryLink } from '../../api'

export type RepoChoice = { selected: boolean; alias: string; base_branch: string; read_only: boolean }

export type FormState = {
  slug: string
  name: string
  sandbox_id: string
  claude_md: string
  plan_mode_enabled: boolean
  require_ticket: boolean
  repos: Record<string, RepoChoice>
}

export const EMPTY_FORM: FormState = { slug: '', name: '', sandbox_id: '', claude_md: '', plan_mode_enabled: false, require_ticket: false, repos: {} }

export const SYNC_COLORS: Record<string, string> = { synced: 'green', pending: 'yellow', error: 'red' }

export function formFromWorkspace(ws: AdminWorkspace): FormState {
  const repos: Record<string, RepoChoice> = {}
  for (const link of ws.repositories) {
    repos[link.repository_id] = {
      selected: true,
      alias: link.alias,
      base_branch: link.base_branch,
      read_only: link.read_only,
    }
  }
  return { slug: ws.slug, name: ws.name, sandbox_id: ws.sandbox_id, claude_md: ws.claude_md, plan_mode_enabled: ws.plan_mode_enabled,
    require_ticket: ws.require_ticket,
    repos,
  }
}

export function linksFromForm(form: FormState): WorkspaceRepositoryLink[] {
  return Object.entries(form.repos)
    .filter(([, choice]) => choice.selected)
    .map(([repository_id, choice]) => ({
      repository_id,
      alias: choice.alias.trim() || null,
      base_branch: choice.base_branch.trim(),
      read_only: choice.read_only,
    }))
}
