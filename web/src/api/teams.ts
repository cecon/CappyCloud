import { apiFetch, formatApiErrorPayload } from './http'

// ── Times do workspace (relatório por time) ─────────────────────────────────

export type WorkspaceTeam = { id: string; name: string; members: number }

async function teamsRequest<T>(
  token: string,
  path: string,
  fallback: string,
  init: RequestInit = {},
): Promise<T> {
  const res = await apiFetch(path, {
    ...init,
    headers: {
      Authorization: `Bearer ${token}`,
      ...(init.body ? { 'Content-Type': 'application/json' } : {}),
      ...(init.headers ?? {}),
    },
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || fallback)
  }
  return (res.status === 204 ? undefined : await res.json()) as T
}

const teamsPath = (workspaceId: string) => `/api/admin/workspaces/${workspaceId}/teams`

export function fetchWorkspaceTeams(token: string, workspaceId: string): Promise<WorkspaceTeam[]> {
  return teamsRequest(token, teamsPath(workspaceId), 'Falha ao carregar os times')
}

export function createWorkspaceTeam(token: string, workspaceId: string, name: string): Promise<WorkspaceTeam> {
  return teamsRequest(token, teamsPath(workspaceId), 'Falha ao criar o time', {
    method: 'POST',
    body: JSON.stringify({ name }),
  })
}

export function renameWorkspaceTeam(
  token: string,
  workspaceId: string,
  teamId: string,
  name: string,
): Promise<WorkspaceTeam> {
  return teamsRequest(token, `${teamsPath(workspaceId)}/${teamId}`, 'Falha ao renomear o time', {
    method: 'PATCH',
    body: JSON.stringify({ name }),
  })
}

export function deleteWorkspaceTeam(token: string, workspaceId: string, teamId: string): Promise<void> {
  return teamsRequest(token, `${teamsPath(workspaceId)}/${teamId}`, 'Falha ao apagar o time', {
    method: 'DELETE',
  })
}

/** `workspace_id → team_id` da pessoa (só onde tem time). */
export function fetchUserWorkspaceTeams(token: string, userId: string): Promise<Record<string, string>> {
  return teamsRequest(
    token,
    `/api/admin/users/${userId}/access/workspaces/teams`,
    'Falha ao carregar os times da pessoa',
  )
}

/** Define o time da pessoa no workspace (`null` = sem time); concede o acesso se faltar. */
export function setUserWorkspaceTeam(
  token: string,
  userId: string,
  workspaceId: string,
  teamId: string | null,
): Promise<void> {
  return teamsRequest(
    token,
    `/api/admin/users/${userId}/access/workspaces/${workspaceId}/team`,
    'Falha ao mudar o time',
    { method: 'PUT', body: JSON.stringify({ team_id: teamId }) },
  )
}
