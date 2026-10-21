import { useCallback, useEffect, useMemo, useState } from 'react'
import { Alert, Button, Container, Group, Loader, Paper, Stack, Text, Title } from '@/components/ui/legacy'
import {
  type AdminWorkspace,
  createAdminWorkspace,
  errorToUserMessage,
  fetchAdminWorkspaces,
  fetchRepositories,
  fetchSandboxes,
  getToken,
  type Repository,
  type Sandbox,
  updateAdminWorkspace,
} from '../api'
import { WorkspaceKnowledgeModal } from '../components/WorkspaceKnowledgeModal'
import { useAdminWorkspaceIds } from '../hooks/useAdminWorkspaceIds'
import { EMPTY_FORM, type FormState, formFromWorkspace, linksFromForm } from './admin-workspaces/formState'
import { WorkspaceFormModal } from './admin-workspaces/WorkspaceFormModal'
import { WorkspacesTable } from './admin-workspaces/WorkspacesTable'

/**
 * Workspaces: pasta de trabalho numa sandbox que agrupa repositórios do
 * catálogo, com CLAUDE.md próprio. O super admin cria e edita tudo; o admin de
 * workspace vê só os dele e muda CLAUDE.md, chamado obrigatório e modo de planejamento.
 */
export function AdminWorkspacesPage() {
  const limited = useAdminWorkspaceIds() !== null
  const [workspaces, setWorkspaces] = useState<AdminWorkspace[] | null>(null)
  const [sandboxes, setSandboxes] = useState<Sandbox[]>([])
  const [repositories, setRepositories] = useState<Repository[]>([])
  const [loadError, setLoadError] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [editing, setEditing] = useState<AdminWorkspace | null>(null)
  const [formOpen, setFormOpen] = useState(false)
  const [form, setForm] = useState<FormState>(EMPTY_FORM)
  const [formError, setFormError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [busyId, setBusyId] = useState<string | null>(null)
  const [knowledgeOf, setKnowledgeOf] = useState<AdminWorkspace | null>(null)

  const reload = useCallback(async () => {
    const token = getToken()
    if (!token) return
    try {
      // Admin de workspace não lê o catálogo de sandboxes e repositórios.
      const [ws, sb, repos] = await Promise.all([
        fetchAdminWorkspaces(token),
        limited ? Promise.resolve([]) : fetchSandboxes(token),
        limited ? Promise.resolve([]) : fetchRepositories(token),
      ])
      setWorkspaces(ws)
      setSandboxes(sb)
      setRepositories(repos)
      setLoadError(null)
    } catch (err) {
      setLoadError(errorToUserMessage(err))
    }
  }, [limited])

  useEffect(() => {
    void reload()
  }, [reload])

  // Enquanto houver sincronização pendente, acompanha o watchdog.
  useEffect(() => {
    if (!workspaces?.some((ws) => ws.sync_status === 'pending')) return
    const timer = window.setInterval(() => void reload(), 4000)
    return () => window.clearInterval(timer)
  }, [workspaces, reload])

  const sandboxName = useMemo(
    () => new Map(sandboxes.map((sandbox) => [sandbox.id, sandbox.name])),
    [sandboxes],
  )

  function openCreate() {
    setEditing(null)
    setForm({ ...EMPTY_FORM, sandbox_id: sandboxes[0]?.id ?? '' })
    setFormError(null)
    setFormOpen(true)
  }

  function openEdit(ws: AdminWorkspace) {
    setEditing(ws)
    setForm(formFromWorkspace(ws))
    setFormError(null)
    setFormOpen(true)
  }

  async function save() {
    const token = getToken()
    if (!token) return
    setSaving(true)
    setFormError(null)
    try {
      const repositories = linksFromForm(form)
      if (editing && limited) {
        await updateAdminWorkspace(token, editing.id, {
          claude_md: form.claude_md,
          plan_mode_enabled: form.plan_mode_enabled,
          require_ticket: form.require_ticket,
        })
      } else if (editing) {
        await updateAdminWorkspace(token, editing.id, {
          name: form.name,
          claude_md: form.claude_md,
          plan_mode_enabled: form.plan_mode_enabled,
          require_ticket: form.require_ticket,
          repositories,
        })
      } else {
        await createAdminWorkspace(token, {
          slug: form.slug.trim(),
          name: form.name,
          sandbox_id: form.sandbox_id,
          claude_md: form.claude_md,
          plan_mode_enabled: form.plan_mode_enabled,
          require_ticket: form.require_ticket,
          repositories,
        })
      }
      setFormOpen(false)
      await reload()
    } catch (err) {
      setFormError(errorToUserMessage(err))
    } finally {
      setSaving(false)
    }
  }

  async function runAction(id: string, action: (token: string) => Promise<unknown>) {
    const token = getToken()
    if (!token) return
    setBusyId(id)
    setActionError(null)
    try {
      await action(token)
      await reload()
    } catch (err) {
      setActionError(errorToUserMessage(err))
    } finally {
      setBusyId(null)
    }
  }

  return (
    <Container size="lg" py="xl">
      <Stack gap="lg">
        <Group justify="space-between" align="flex-end">
          <Stack gap={4}>
            <Title order={2}>Workspaces</Title>
            <Text c="dimmed" size="sm">
              Pasta de trabalho numa sandbox com vários repositórios e um CLAUDE.md próprio. Cada
              conversa abre todos os repositórios do workspace.
            </Text>
          </Stack>
          {!limited && (
            <Button onClick={openCreate} disabled={sandboxes.length === 0}>
              Novo workspace
            </Button>
          )}
        </Group>

        {actionError && (
          <Alert color="red" title="Falha" withCloseButton onClose={() => setActionError(null)}>
            {actionError}
          </Alert>
        )}

        <Paper withBorder p="md" radius="md">
          {loadError ? (
            <Alert color="red" title="Não foi possível carregar workspaces">
              {loadError}
            </Alert>
          ) : workspaces === null ? (
            <Group justify="center" py="xl">
              <Loader />
            </Group>
          ) : workspaces.length === 0 ? (
            <Text c="dimmed" ta="center" py="xl">
              Nenhum workspace cadastrado.
            </Text>
          ) : (
            <WorkspacesTable
              workspaces={workspaces}
              sandboxName={sandboxName}
              busyId={busyId}
              onEdit={openEdit}
              onKnowledge={setKnowledgeOf}
              runAction={(id, action) => void runAction(id, action)}
              limited={limited}
            />
          )}
        </Paper>
      </Stack>

      <WorkspaceKnowledgeModal key={knowledgeOf?.id ?? 'none'} workspace={knowledgeOf} onClose={() => setKnowledgeOf(null)} />

      <WorkspaceFormModal
        limited={limited}
        opened={formOpen}
        editing={editing}
        form={form}
        setForm={setForm}
        formError={formError}
        saving={saving}
        sandboxes={sandboxes}
        repositories={repositories}
        onClose={() => setFormOpen(false)}
        onSave={() => void save()}
      />
    </Container>
  )
}
