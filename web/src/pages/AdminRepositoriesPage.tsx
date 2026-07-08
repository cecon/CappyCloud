import { useCallback, useEffect, useState } from 'react'
import {
  Alert,
  Badge,
  Button,
  Container,
  Group,
  Loader,
  Modal,
  Paper,
  Select,
  Stack,
  Table,
  Text,
  TextInput,
  Title,
} from '@mantine/core'
import { IconFileText, IconPencil, IconRefresh, IconTrash } from '@tabler/icons-react'
import {
  createRepository,
  deleteRepository,
  errorToUserMessage,
  fetchRepositories,
  fetchSandboxes,
  getToken,
  type Repository,
  type RepositoryCreate,
  type Sandbox,
  syncRepository,
  updateRepository,
} from '../api'
import { RepositoryDocumentsModal } from '../components/RepositoryDocumentsModal'
import { ActionsCell, ActionsHeader, RowActionIcon } from '../components/TableActions'

type FormState = {
  slug: string
  name: string
  clone_url: string
  default_branch: string
  confluence_url: string
  confluence_space: string
  confluence_labels: string
  pat_token: string
  sandbox_id: string | null
}

const EMPTY_FORM: FormState = {
  slug: '',
  name: '',
  clone_url: '',
  default_branch: 'main',
  confluence_url: '',
  confluence_space: '',
  confluence_labels: '',
  pat_token: '',
  sandbox_id: null,
}

function parseLabels(value: string): string[] {
  const seen = new Set<string>()
  return value
    .split(',')
    .map((label) => label.trim().toLowerCase())
    .filter((label) => {
      if (!label || seen.has(label)) return false
      seen.add(label)
      return true
    })
}

function labelsToText(labels: string[] | null | undefined): string {
  return labels?.join(', ') ?? ''
}

function formFromRepository(repo: Repository): FormState {
  return {
    slug: repo.slug,
    name: repo.name,
    clone_url: repo.clone_url,
    default_branch: repo.default_branch,
    confluence_url: repo.confluence_url,
    confluence_space: repo.confluence_space,
    confluence_labels: labelsToText(repo.confluence_labels),
    pat_token: '',
    sandbox_id: repo.sandbox_id,
  }
}

function statusColor(s: string): string {
  if (s === 'cloned') return 'green'
  if (s === 'cloning') return 'yellow'
  if (s === 'error') return 'red'
  return 'gray'
}

export function AdminRepositoriesPage() {
  const [repos, setRepos] = useState<Repository[] | null>(null)
  const [sandboxes, setSandboxes] = useState<Sandbox[]>([])
  const [loadError, setLoadError] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [busyId, setBusyId] = useState<string | null>(null)

  const [createOpen, setCreateOpen] = useState(false)
  const [editingRepo, setEditingRepo] = useState<Repository | null>(null)
  const [documentsRepo, setDocumentsRepo] = useState<Repository | null>(null)
  const [form, setForm] = useState<FormState>(EMPTY_FORM)
  const [creating, setCreating] = useState(false)
  const [updating, setUpdating] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)

  const reload = useCallback(async () => {
    const token = getToken()
    if (!token) return
    try {
      const [rs, sbs] = await Promise.all([fetchRepositories(token), fetchSandboxes(token)])
      setRepos(rs)
      setSandboxes(sbs)
      setLoadError(null)
    } catch (err) {
      setLoadError(errorToUserMessage(err))
    }
  }, [])

  useEffect(() => {
    void reload()
  }, [reload])

  async function handleCreate() {
    const token = getToken()
    if (!token) return
    if (!form.slug.trim() || !form.name.trim() || !form.clone_url.trim()) {
      setFormError('Slug, nome e clone URL são obrigatórios.')
      return
    }
    setCreating(true)
    setFormError(null)
    try {
      await createRepository(token, buildPayload())
      setForm(EMPTY_FORM)
      setCreateOpen(false)
      await reload()
    } catch (err) {
      setFormError(errorToUserMessage(err))
    } finally {
      setCreating(false)
    }
  }

  async function handleUpdate() {
    const token = getToken()
    if (!token || !editingRepo) return
    if (!form.slug.trim() || !form.name.trim() || !form.clone_url.trim()) {
      setFormError('Slug, nome e clone URL são obrigatórios.')
      return
    }
    setUpdating(true)
    setFormError(null)
    try {
      await updateRepository(token, editingRepo.id, buildPayload(editingRepo))
      setForm(EMPTY_FORM)
      setEditingRepo(null)
      await reload()
    } catch (err) {
      setFormError(errorToUserMessage(err))
    } finally {
      setUpdating(false)
    }
  }

  function buildPayload(existing?: Repository): RepositoryCreate {
    return {
      slug: form.slug.trim(),
      name: form.name.trim(),
      clone_url: form.clone_url.trim(),
      default_branch: form.default_branch.trim() || 'main',
      confluence_url: form.confluence_url.trim(),
      confluence_space: form.confluence_space.trim(),
      confluence_labels: parseLabels(form.confluence_labels),
      pat_token: form.pat_token.trim() || null,
      provider_id: existing?.provider_id ?? null,
      sandbox_id: form.sandbox_id || null,
      signoz_service_name: existing?.signoz_service_name ?? null,
    }
  }

  function openEdit(repo: Repository) {
    setCreateOpen(false)
    setEditingRepo(repo)
    setForm(formFromRepository(repo))
    setFormError(null)
  }

  async function handleSync(repoId: string) {
    const token = getToken()
    if (!token) return
    setBusyId(repoId)
    setActionError(null)
    try {
      await syncRepository(token, repoId)
      await reload()
    } catch (err) {
      setActionError(errorToUserMessage(err))
    } finally {
      setBusyId(null)
    }
  }

  async function handleDelete(repoId: string) {
    if (!window.confirm('Remover este repositório? A operação dispara remoção do sandbox também.')) {
      return
    }
    const token = getToken()
    if (!token) return
    setBusyId(repoId)
    setActionError(null)
    try {
      await deleteRepository(token, repoId)
      await reload()
    } catch (err) {
      setActionError(errorToUserMessage(err))
    } finally {
      setBusyId(null)
    }
  }

  const sandboxOptions = [
    { value: '', label: '— Nenhum —' },
    ...sandboxes.map((s) => ({ value: s.id, label: s.name })),
  ]

  return (
    <Container size="lg" py="xl">
      <Stack gap="lg">
        <Group justify="space-between" align="flex-end">
          <Stack gap={4}>
            <Title order={2}>Repositórios</Title>
            <Text c="dimmed" size="sm">
              Catálogo Git por sandbox. O PAT inline cria um GitProvider implícito; para reutilizar
              credenciais, use a secção de providers no SettingsPage.
            </Text>
          </Stack>
          <Button
            onClick={() => {
              setForm(EMPTY_FORM)
              setFormError(null)
              setEditingRepo(null)
              setCreateOpen(true)
            }}
          >
            Novo repositório
          </Button>
        </Group>

        {actionError && (
          <Alert color="red" title="Falha" withCloseButton onClose={() => setActionError(null)}>
            {actionError}
          </Alert>
        )}

        <Paper withBorder p="md" radius="md">
          {loadError ? (
            <Alert color="red" title="Não foi possível carregar repositórios">
              {loadError}
            </Alert>
          ) : repos === null ? (
            <Group justify="center" py="xl">
              <Loader />
            </Group>
          ) : repos.length === 0 ? (
            <Text c="dimmed" ta="center" py="xl">
              Nenhum repositório cadastrado.
            </Text>
          ) : (
            <Table verticalSpacing="sm" highlightOnHover>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Nome</Table.Th>
                  <Table.Th>Slug</Table.Th>
                  <Table.Th>Clone URL</Table.Th>
                  <Table.Th style={{ width: 120 }}>Branch</Table.Th>
                  <Table.Th>Confluence</Table.Th>
                  <Table.Th style={{ width: 120 }}>Estado</Table.Th>
                  <ActionsHeader width={178} />
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {repos.map((r) => (
                  <Table.Tr key={r.id}>
                    <Table.Td>
                      <Text fw={500}>{r.name}</Text>
                    </Table.Td>
                    <Table.Td>
                      <Badge variant="light" color="gray">
                        {r.slug}
                      </Badge>
                    </Table.Td>
                    <Table.Td>
                      <Text size="xs" c="dimmed" style={{ wordBreak: 'break-all' }}>
                        {r.clone_url}
                      </Text>
                    </Table.Td>
                    <Table.Td>
                      <Text size="sm">{r.default_branch}</Text>
                    </Table.Td>
                    <Table.Td>
                      <Stack gap={4}>
                        {r.confluence_url ? (
                          <Text size="xs" c="dimmed">
                            {r.confluence_space || 'Sem space'}
                          </Text>
                        ) : (
                          <Text size="xs" c="dimmed">
                            -
                          </Text>
                        )}
                        {r.confluence_labels?.length > 0 && (
                          <Group gap={4}>
                            {r.confluence_labels.map((label) => (
                              <Badge key={label} size="xs" variant="light" color="blue">
                                {label}
                              </Badge>
                            ))}
                          </Group>
                        )}
                      </Stack>
                    </Table.Td>
                    <Table.Td>
                      <Badge color={statusColor(r.sandbox_status)} variant="light">
                        {r.sandbox_status}
                      </Badge>
                    </Table.Td>
                    <ActionsCell>
                      <RowActionIcon
                        label="Importar documentos"
                        color="violet"
                        disabled={busyId !== null}
                        onClick={() => setDocumentsRepo(r)}
                      >
                        <IconFileText size={16} />
                      </RowActionIcon>
                      <RowActionIcon
                        label="Editar repositório"
                        color="gray"
                        disabled={busyId !== null}
                        onClick={() => openEdit(r)}
                      >
                        <IconPencil size={16} />
                      </RowActionIcon>
                      <RowActionIcon
                        label="Sincronizar repositório"
                        color="blue"
                        loading={busyId === r.id}
                        disabled={busyId !== null || !r.sandbox_id}
                        onClick={() => void handleSync(r.id)}
                      >
                        <IconRefresh size={16} />
                      </RowActionIcon>
                      <RowActionIcon
                        label="Remover repositório"
                        color="red"
                        disabled={busyId !== null}
                        onClick={() => void handleDelete(r.id)}
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

      <RepositoryDocumentsModal
        opened={documentsRepo !== null}
        repository={documentsRepo}
        token={getToken() ?? ''}
        onClose={() => setDocumentsRepo(null)}
      />

      <Modal
        opened={createOpen}
        onClose={() => setCreateOpen(false)}
        title="Novo repositório"
        centered
        size="lg"
      >
        <Stack gap="md">
          {formError && (
            <Alert color="red" title="Não foi possível criar">
              {formError}
            </Alert>
          )}
          <TextInput
            label="Slug"
            description="Identificador curto; usado em URLs e nomes de pastas."
            value={form.slug}
            onChange={(e) => setForm({ ...form, slug: e.currentTarget.value })}
            required
          />
          <TextInput
            label="Nome"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.currentTarget.value })}
            required
          />
          <TextInput
            label="Clone URL"
            placeholder="https://github.com/org/repo.git"
            value={form.clone_url}
            onChange={(e) => setForm({ ...form, clone_url: e.currentTarget.value })}
            required
          />
          <TextInput
            label="Branch default"
            value={form.default_branch}
            onChange={(e) => setForm({ ...form, default_branch: e.currentTarget.value })}
          />
          <TextInput
            label="Confluence URL"
            placeholder="https://confluence.example.com"
            value={form.confluence_url}
            onChange={(e) => setForm({ ...form, confluence_url: e.currentTarget.value })}
          />
          <TextInput
            label="Confluence space"
            placeholder="Frontend"
            value={form.confluence_space}
            onChange={(e) => setForm({ ...form, confluence_space: e.currentTarget.value })}
          />
          <TextInput
            label="Rótulos Confluence"
            placeholder="react, react-dom, react-native"
            value={form.confluence_labels}
            onChange={(e) => setForm({ ...form, confluence_labels: e.currentTarget.value })}
          />
          <TextInput
            label="PAT (opcional)"
            description="Cria um GitProvider implícito com o token cifrado."
            type="password"
            autoComplete="off"
            value={form.pat_token}
            onChange={(e) => setForm({ ...form, pat_token: e.currentTarget.value })}
          />
          <Select
            label="Sandbox"
            description="Onde o repo será clonado. Deixe vazio para usar o primeiro ativo."
            data={sandboxOptions}
            value={form.sandbox_id ?? ''}
            onChange={(v) => setForm({ ...form, sandbox_id: v || null })}
          />
          <Group justify="flex-end" mt="sm">
            <Button variant="default" onClick={() => setCreateOpen(false)} disabled={creating}>
              Cancelar
            </Button>
            <Button onClick={() => void handleCreate()} loading={creating}>
              Criar
            </Button>
          </Group>
        </Stack>
      </Modal>

      <Modal
        opened={editingRepo !== null}
        onClose={() => {
          setEditingRepo(null)
          setForm(EMPTY_FORM)
          setFormError(null)
        }}
        title={editingRepo ? `Editar ${editingRepo.name}` : 'Editar repositório'}
        centered
        size="lg"
      >
        <Stack gap="md">
          {formError && (
            <Alert color="red" title="Não foi possível atualizar">
              {formError}
            </Alert>
          )}
          <TextInput
            label="Slug"
            value={form.slug}
            onChange={(e) => setForm({ ...form, slug: e.currentTarget.value })}
            required
          />
          <TextInput
            label="Nome"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.currentTarget.value })}
            required
          />
          <TextInput
            label="Clone URL"
            value={form.clone_url}
            onChange={(e) => setForm({ ...form, clone_url: e.currentTarget.value })}
            required
          />
          <TextInput
            label="Branch default"
            value={form.default_branch}
            onChange={(e) => setForm({ ...form, default_branch: e.currentTarget.value })}
          />
          <TextInput
            label="Confluence URL"
            placeholder="https://confluence.example.com"
            value={form.confluence_url}
            onChange={(e) => setForm({ ...form, confluence_url: e.currentTarget.value })}
          />
          <TextInput
            label="Confluence space"
            placeholder="Frontend"
            value={form.confluence_space}
            onChange={(e) => setForm({ ...form, confluence_space: e.currentTarget.value })}
          />
          <TextInput
            label="Rótulos Confluence"
            placeholder="kubernetes, kubelet"
            value={form.confluence_labels}
            onChange={(e) => setForm({ ...form, confluence_labels: e.currentTarget.value })}
          />
          <TextInput
            label="PAT (opcional)"
            type="password"
            autoComplete="off"
            value={form.pat_token}
            onChange={(e) => setForm({ ...form, pat_token: e.currentTarget.value })}
          />
          <Select
            label="Sandbox"
            data={sandboxOptions}
            value={form.sandbox_id ?? ''}
            onChange={(v) => setForm({ ...form, sandbox_id: v || null })}
          />
          <Group justify="flex-end" mt="sm">
            <Button
              variant="default"
              onClick={() => {
                setEditingRepo(null)
                setForm(EMPTY_FORM)
                setFormError(null)
              }}
              disabled={updating}
            >
              Cancelar
            </Button>
            <Button onClick={() => void handleUpdate()} loading={updating}>
              Salvar
            </Button>
          </Group>
        </Stack>
      </Modal>
    </Container>
  )
}
