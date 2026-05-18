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
} from '../api'

type FormState = {
  slug: string
  name: string
  clone_url: string
  default_branch: string
  pat_token: string
  sandbox_id: string | null
}

const EMPTY_FORM: FormState = {
  slug: '',
  name: '',
  clone_url: '',
  default_branch: 'main',
  pat_token: '',
  sandbox_id: null,
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
  const [form, setForm] = useState<FormState>(EMPTY_FORM)
  const [creating, setCreating] = useState(false)
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
      const payload: RepositoryCreate = {
        slug: form.slug.trim(),
        name: form.name.trim(),
        clone_url: form.clone_url.trim(),
        default_branch: form.default_branch.trim() || 'main',
        pat_token: form.pat_token.trim() || null,
        sandbox_id: form.sandbox_id || null,
      }
      await createRepository(token, payload)
      setForm(EMPTY_FORM)
      setCreateOpen(false)
      await reload()
    } catch (err) {
      setFormError(errorToUserMessage(err))
    } finally {
      setCreating(false)
    }
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
                  <Table.Th style={{ width: 120 }}>Estado</Table.Th>
                  <Table.Th style={{ width: 180 }}>Ações</Table.Th>
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
                      <Badge color={statusColor(r.sandbox_status)} variant="light">
                        {r.sandbox_status}
                      </Badge>
                    </Table.Td>
                    <Table.Td>
                      <Group gap="xs">
                        <Button
                          size="xs"
                          variant="light"
                          loading={busyId === r.id}
                          disabled={busyId !== null || !r.sandbox_id}
                          onClick={() => void handleSync(r.id)}
                        >
                          Sincronizar
                        </Button>
                        <Button
                          size="xs"
                          variant="subtle"
                          color="red"
                          disabled={busyId !== null}
                          onClick={() => void handleDelete(r.id)}
                        >
                          Remover
                        </Button>
                      </Group>
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          )}
        </Paper>
      </Stack>

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
    </Container>
  )
}
