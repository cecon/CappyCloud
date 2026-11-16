import { type FormEvent, useEffect, useState } from 'react'
import { Check, Pencil, Plus, Trash2, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { type AdminWorkspace, errorToUserMessage, getToken } from '../api'
import {
  type WorkspaceTeam,
  createWorkspaceTeam,
  deleteWorkspaceTeam,
  fetchWorkspaceTeams,
  renameWorkspaceTeam,
} from '../api/teams'

type Props = {
  workspace: AdminWorkspace | null
  onClose: () => void
}

/** Times do workspace: o relatório agrupa as pessoas por eles. Pessoa ↔ time fica em Usuários → Acessos. */
export function WorkspaceTeamsDialog({ workspace, onClose }: Props) {
  const [teams, setTeams] = useState<WorkspaceTeam[] | null>(null)
  const [name, setName] = useState('')
  const [editing, setEditing] = useState<{ id: string; name: string } | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const token = getToken()
    if (!workspace || !token) return
    setTeams(null)
    setError(null)
    setName('')
    setEditing(null)
    fetchWorkspaceTeams(token, workspace.id)
      .then(setTeams)
      .catch((err) => setError(errorToUserMessage(err)))
  }, [workspace])

  async function run(action: (token: string, wsId: string) => Promise<unknown>) {
    const token = getToken()
    if (!token || !workspace) return false
    setBusy(true)
    setError(null)
    try {
      await action(token, workspace.id)
      setTeams(await fetchWorkspaceTeams(token, workspace.id))
      return true
    } catch (err) {
      setError(errorToUserMessage(err))
      return false
    } finally {
      setBusy(false)
    }
  }

  async function create(event: FormEvent) {
    event.preventDefault()
    if (!name.trim()) return
    if (await run((token, wsId) => createWorkspaceTeam(token, wsId, name))) setName('')
  }

  async function rename(event: FormEvent) {
    event.preventDefault()
    if (!editing?.name.trim()) return
    if (await run((token, wsId) => renameWorkspaceTeam(token, wsId, editing.id, editing.name))) setEditing(null)
  }

  function remove(team: WorkspaceTeam) {
    const who = team.members === 1 ? '1 pessoa fica' : `${team.members} pessoas ficam`
    const note = team.members > 0 ? ` ${who} sem time.` : ''
    if (!window.confirm(`Apagar o time "${team.name}"?${note}`)) return
    void run((token, wsId) => deleteWorkspaceTeam(token, wsId, team.id))
  }

  return (
    <Dialog open={workspace !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Times · {workspace?.name}</DialogTitle>
          <DialogDescription>
            O relatório agrupa as consultas por time. Para colocar alguém num time, use Usuários → Acessos →
            Workspaces.
          </DialogDescription>
        </DialogHeader>

        {error && <p className="rounded-md bg-destructive/10 p-2 text-sm text-destructive">{error}</p>}

        <form onSubmit={(e) => void create(e)} className="flex gap-2">
          <Input
            value={name}
            maxLength={128}
            placeholder="Nome do time (ex.: PROTHEUS SPED)"
            onChange={(e) => setName(e.target.value)}
            aria-label="Nome do novo time"
          />
          <Button type="submit" disabled={busy || !name.trim()}>
            <Plus className="size-4" />
            Adicionar
          </Button>
        </form>

        <ul className="divide-y divide-border rounded-md border border-border">
          {teams === null && !error && <li className="p-3 text-sm text-muted-foreground">Carregando…</li>}
          {teams?.length === 0 && <li className="p-3 text-sm text-muted-foreground">Nenhum time ainda.</li>}
          {teams?.map((team) =>
            editing?.id === team.id ? (
              <li key={team.id} className="p-2">
                <form onSubmit={(e) => void rename(e)} className="flex gap-2">
                  <Input
                    autoFocus
                    value={editing.name}
                    maxLength={128}
                    onChange={(e) => setEditing({ id: team.id, name: e.target.value })}
                    aria-label={`Novo nome de ${team.name}`}
                  />
                  <Button type="submit" size="icon" variant="outline" disabled={busy} aria-label="Salvar nome">
                    <Check className="size-4" />
                  </Button>
                  <Button type="button" size="icon" variant="ghost" onClick={() => setEditing(null)} aria-label="Cancelar">
                    <X className="size-4" />
                  </Button>
                </form>
              </li>
            ) : (
              <li key={team.id} className="flex items-center gap-2 p-2 pl-3">
                <span className="flex-1 text-sm font-medium">{team.name}</span>
                <span className="text-xs tabular-nums text-muted-foreground">
                  {team.members === 1 ? '1 pessoa' : `${team.members} pessoas`}
                </span>
                <Button
                  size="icon"
                  variant="ghost"
                  disabled={busy}
                  onClick={() => setEditing({ id: team.id, name: team.name })}
                  aria-label={`Renomear ${team.name}`}
                >
                  <Pencil className="size-4" />
                </Button>
                <Button
                  size="icon"
                  variant="ghost"
                  disabled={busy}
                  onClick={() => remove(team)}
                  aria-label={`Apagar ${team.name}`}
                >
                  <Trash2 className="size-4 text-destructive" />
                </Button>
              </li>
            ),
          )}
        </ul>
      </DialogContent>
    </Dialog>
  )
}
