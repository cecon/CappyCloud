import { useEffect, useState } from 'react'
import { type AdminWorkspace, errorToUserMessage, getToken } from '../../api'
import { type WorkspaceTeam, fetchUserWorkspaceTeams, fetchWorkspaceTeams, setUserWorkspaceTeam } from '../../api/teams'

type Props = {
  userId: string
  /** Workspaces liberados para a pessoa (o time só existe dentro de um workspace). */
  workspaces: AdminWorkspace[]
  onError: (message: string) => void
}

const selectClass = 'h-9 min-w-[14rem] rounded-md border border-input bg-background px-3 text-sm'

/** Time da pessoa em cada workspace liberado; o relatório agrupa as consultas por ele. */
export function WorkspaceTeamPicker({ userId, workspaces, onError }: Props) {
  const [teams, setTeams] = useState<Record<string, WorkspaceTeam[]>>({})
  const [chosen, setChosen] = useState<Record<string, string>>({})
  const [busy, setBusy] = useState<string | null>(null)
  const ids = workspaces.map((ws) => ws.id).join(',')

  useEffect(() => {
    const token = getToken()
    if (!token || !ids) return
    void Promise.all([
      fetchUserWorkspaceTeams(token, userId),
      ...ids.split(',').map((id) => fetchWorkspaceTeams(token, id).then((list) => [id, list] as const)),
    ])
      .then(([mine, ...lists]) => {
        setChosen(mine as Record<string, string>)
        setTeams(Object.fromEntries(lists as (readonly [string, WorkspaceTeam[]])[]))
      })
      .catch((err) => onError(errorToUserMessage(err)))
  }, [userId, ids, onError])

  async function choose(workspaceId: string, teamId: string) {
    const token = getToken()
    if (!token) return
    const previous = chosen[workspaceId]
    setBusy(workspaceId)
    setChosen((prev) => ({ ...prev, [workspaceId]: teamId }))
    try {
      await setUserWorkspaceTeam(token, userId, workspaceId, teamId || null)
    } catch (err) {
      setChosen((prev) => ({ ...prev, [workspaceId]: previous ?? '' }))
      onError(errorToUserMessage(err))
    } finally {
      setBusy(null)
    }
  }

  const withTeams = workspaces.filter((ws) => (teams[ws.id]?.length ?? 0) > 0)
  return (
    <div className="mt-5 space-y-2">
      <p className="text-sm font-medium">Time no workspace</p>
      <p className="text-xs text-muted-foreground">
        O relatório mostra as consultas por time. Os times são cadastrados em Workspaces → Times.
      </p>
      {withTeams.length === 0 ? (
        <p className="text-xs text-muted-foreground">Nenhum workspace liberado tem times cadastrados.</p>
      ) : (
        <ul className="divide-y divide-border rounded-md border border-border">
          {withTeams.map((ws) => (
            <li key={ws.id} className="flex flex-wrap items-center justify-between gap-2 p-2 pl-3">
              <span className="text-sm">{ws.name}</span>
              <select
                className={selectClass}
                value={chosen[ws.id] ?? ''}
                disabled={busy === ws.id}
                onChange={(e) => void choose(ws.id, e.target.value)}
                aria-label={`Time em ${ws.name}`}
              >
                <option value="">Sem time</option>
                {teams[ws.id].map((team) => (
                  <option key={team.id} value={team.id}>
                    {team.name}
                  </option>
                ))}
              </select>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
