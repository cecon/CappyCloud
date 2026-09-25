import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Alert,
  Badge,
  Button,
  Checkbox,
  Container,
  Group,
  Loader,
  Modal,
  Paper,
  Select,
  Stack,
  Table,
  Text,
  Textarea,
  TextInput,
  Title,
} from '@/components/ui/legacy'
import { IconBrain, IconPencil, IconRefresh, IconTrash } from '@tabler/icons-react'
import {
  type AdminWorkspace,
  createAdminWorkspace,
  deleteAdminWorkspace,
  errorToUserMessage,
  fetchAdminWorkspaces,
  fetchRepositories,
  fetchSandboxes,
  getToken,
  type Repository,
  type Sandbox,
  syncAdminWorkspace,
  updateAdminWorkspace,
  type WorkspaceRepositoryLink,
} from '../api'
import { ActionsCell, ActionsHeader, RowActionIcon } from '../components/TableActions'
import { WorkspaceKnowledgeBadges } from '../components/WorkspaceKnowledgeBadges'
import { WorkspaceKnowledgeModal } from '../components/WorkspaceKnowledgeModal'

type RepoChoice = { selected: boolean; alias: string; base_branch: string; read_only: boolean }

type FormState = {
  slug: string
  name: string
  sandbox_id: string
  claude_md: string
  repos: Record<string, RepoChoice>
}

const EMPTY_FORM: FormState = { slug: '', name: '', sandbox_id: '', claude_md: '', repos: {} }

const SYNC_COLORS: Record<string, string> = { synced: 'green', pending: 'yellow', error: 'red' }

function formFromWorkspace(ws: AdminWorkspace): FormState {
  const repos: Record<string, RepoChoice> = {}
  for (const link of ws.repositories) {
    repos[link.repository_id] = {
      selected: true,
      alias: link.alias,
      base_branch: link.base_branch,
      read_only: link.read_only,
    }
  }
  return { slug: ws.slug, name: ws.name, sandbox_id: ws.sandbox_id, claude_md: ws.claude_md, repos }
}

function linksFromForm(form: FormState): WorkspaceRepositoryLink[] {
  return Object.entries(form.repos)
    .filter(([, choice]) => choice.selected)
    .map(([repository_id, choice]) => ({
      repository_id,
      alias: choice.alias.trim() || null,
      base_branch: choice.base_branch.trim(),
      read_only: choice.read_only,
    }))
}

/**
 * Workspaces: pasta de trabalho numa sandbox que agrupa repositórios do
 * catálogo, com CLAUDE.md próprio. Só o super admin cria e edita.
 */
export function AdminWorkspacesPage() {
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
      const [ws, sb, repos] = await Promise.all([
        fetchAdminWorkspaces(token),
        fetchSandboxes(token),
        fetchRepositories(token),
      ])
      setWorkspaces(ws)
      setSandboxes(sb)
      setRepositories(repos)
      setLoadError(null)
    } catch (err) {
      setLoadError(errorToUserMessage(err))
    }
  }, [])

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
  const sandboxRepos = repositories.filter((repo) => repo.sandbox_id === form.sandbox_id)

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

  function updateRepo(repoId: string, patch: Partial<RepoChoice>, fallbackAlias: string) {
    setForm((prev) => {
      const current = prev.repos[repoId] ?? {
        selected: false,
        alias: fallbackAlias,
        base_branch: '',
        read_only: false,
      }
      return { ...prev, repos: { ...prev.repos, [repoId]: { ...current, ...patch } } }
    })
  }

  async function save() {
    const token = getToken()
    if (!token) return
    setSaving(true)
    setFormError(null)
    try {
      const repositories = linksFromForm(form)
      if (editing) {
        await updateAdminWorkspace(token, editing.id, {
          name: form.name,
          claude_md: form.claude_md,
          repositories,
        })
      } else {
        await createAdminWorkspace(token, {
          slug: form.slug.trim(),
          name: form.name,
          sandbox_id: form.sandbox_id,
          claude_md: form.claude_md,
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
          <Button onClick={openCreate} disabled={sandboxes.length === 0}>
            Novo workspace
          </Button>
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
            <Table verticalSpacing="sm" highlightOnHover>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Nome</Table.Th>
                  <Table.Th>Slug</Table.Th>
                  <Table.Th>Sandbox</Table.Th>
                  <Table.Th>Repositórios</Table.Th>
                  <Table.Th style={{ width: 120 }}>Sincronização</Table.Th>
                  <Table.Th>Conhecimento</Table.Th>
                  <ActionsHeader width={140} />
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {workspaces.map((ws) => (
                  <Table.Tr key={ws.id}>
                    <Table.Td>
                      <Text fw={500}>{ws.name}</Text>
                    </Table.Td>
                    <Table.Td>
                      <Badge variant="light" color="gray">
                        {ws.slug}
                      </Badge>
                    </Table.Td>
                    <Table.Td>
                      <Text size="sm">{sandboxName.get(ws.sandbox_id) ?? '—'}</Text>
                    </Table.Td>
                    <Table.Td>
                      <Group gap={4}>
                        {ws.repositories.length === 0 && (
                          <Text size="xs" c="dimmed">
                            nenhum
                          </Text>
                        )}
                        {ws.repositories.map((link) => (
                          <Badge
                            key={link.repository_id}
                            size="xs"
                            variant="light"
                            color={link.sandbox_status === 'cloned' ? 'blue' : 'yellow'}
                          >
                            {link.alias}
                            {link.read_only ? ' · leitura' : ''}
                          </Badge>
                        ))}
                      </Group>
                    </Table.Td>
                    <Table.Td>
                      <Badge color={SYNC_COLORS[ws.sync_status] ?? 'gray'} variant="light">
                        {ws.sync_status}
                      </Badge>
                      {ws.sync_error && (
                        <Text size="xs" c="red" title={ws.sync_error}>
                          {ws.sync_error.slice(0, 60)}
                        </Text>
                      )}
                    </Table.Td>
                    <Table.Td>
                      <WorkspaceKnowledgeBadges workspaceId={ws.id} onOpen={() => setKnowledgeOf(ws)} />
                    </Table.Td>
                    <ActionsCell>
                      <RowActionIcon
                        label="Editar workspace"
                        color="gray"
                        disabled={busyId !== null}
                        onClick={() => openEdit(ws)}
                      >
                        <IconPencil size={16} />
                      </RowActionIcon>
                      <RowActionIcon label="Conhecimento (grafo e memória)" color="violet" onClick={() => setKnowledgeOf(ws)}>
                        <IconBrain size={16} />
                      </RowActionIcon>
                      <RowActionIcon
                        label="Sincronizar no sandbox"
                        color="blue"
                        loading={busyId === ws.id}
                        disabled={busyId !== null}
                        onClick={() => void runAction(ws.id, (t) => syncAdminWorkspace(t, ws.id))}
                      >
                        <IconRefresh size={16} />
                      </RowActionIcon>
                      <RowActionIcon
                        label="Remover workspace"
                        color="red"
                        disabled={busyId !== null}
                        onClick={() => {
                          if (!window.confirm(`Remover o workspace ${ws.name}? Os repositórios do catálogo não são afetados.`)) return
                          void runAction(ws.id, (t) => deleteAdminWorkspace(t, ws.id))
                        }}
                      >
                        <IconTrash size={16} />
                      </RowActionIcon>
                    </ActionsCell>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          )}
        </Paper>
      </Stack>

      <WorkspaceKnowledgeModal key={knowledgeOf?.id ?? 'none'} workspace={knowledgeOf} onClose={() => setKnowledgeOf(null)} />

      <Modal
        opened={formOpen}
        onClose={() => setFormOpen(false)}
        title={editing ? `Editar ${editing.name}` : 'Novo workspace'}
        size="xl"
      >
        <Stack gap="md">
          {formError && (
            <Alert color="red" title="Não foi possível salvar">
              {formError}
            </Alert>
          )}
          <Group grow>
            <TextInput
              label="Nome"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.currentTarget.value })}
              required
            />
            <TextInput
              label="Slug"
              description="Minúsculas, números e hífen. Vira a pasta no sandbox."
              value={form.slug}
              disabled={!!editing}
              onChange={(e) => setForm({ ...form, slug: e.currentTarget.value.toLowerCase() })}
              required
            />
          </Group>
          <Select
            label="Sandbox"
            description={editing ? 'Não muda depois de criado.' : 'Só repositórios desta sandbox podem entrar.'}
            data={sandboxes.map((sandbox) => ({ value: sandbox.id, label: sandbox.name }))}
            value={form.sandbox_id}
            disabled={!!editing}
            onChange={(value) => setForm({ ...form, sandbox_id: value ?? '', repos: {} })}
            allowDeselect={false}
          />

          <Stack gap="xs">
            <Text fw={600} size="sm">
              Repositórios
            </Text>
            {sandboxRepos.length === 0 ? (
              <Text size="sm" c="dimmed">
                Nenhum repositório cadastrado nesta sandbox.
              </Text>
            ) : (
              sandboxRepos.map((repo) => {
                const choice = form.repos[repo.id]
                return (
                  <Group key={repo.id} gap="sm" wrap="nowrap">
                    <Checkbox
                      checked={!!choice?.selected}
                      onChange={(e) =>
                        updateRepo(repo.id, { selected: e.currentTarget.checked }, repo.slug)
                      }
                      label={`${repo.name} (${repo.slug})`}
                    />
                    {choice?.selected && (
                      <>
                        <TextInput
                          aria-label={`Alias de ${repo.slug}`}
                          placeholder={`alias (${repo.slug})`}
                          value={choice.alias}
                          onChange={(e) => updateRepo(repo.id, { alias: e.currentTarget.value }, repo.slug)}
                        />
                        <TextInput
                          aria-label={`Branch base de ${repo.slug}`}
                          placeholder={`branch (${repo.default_branch})`}
                          value={choice.base_branch}
                          onChange={(e) =>
                            updateRepo(repo.id, { base_branch: e.currentTarget.value }, repo.slug)
                          }
                        />
                        <Checkbox
                          label="Somente leitura (sem edição nem PR)"
                          checked={choice.read_only}
                          onChange={(e) =>
                            updateRepo(repo.id, { read_only: e.currentTarget.checked }, repo.slug)
                          }
                        />
                      </>
                    )}
                  </Group>
                )
              })
            )}
          </Stack>

          <Textarea
            label="CLAUDE.md do workspace"
            description="Instruções que o agente recebe em todas as conversas deste workspace."
            value={form.claude_md}
            onChange={(e) => setForm({ ...form, claude_md: e.currentTarget.value })}
            minRows={10}
            spellCheck={false}
            style={{ fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace' }}
          />
          <Group justify="flex-end">
            <Button variant="subtle" onClick={() => setFormOpen(false)}>
              Cancelar
            </Button>
            <Button onClick={() => void save()} loading={saving} disabled={saving}>
              Salvar
            </Button>
          </Group>
        </Stack>
      </Modal>
    </Container>
  )
}
