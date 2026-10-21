import { useCallback, useEffect, useState } from 'react'
import {
  Alert,
  Button,
  Container,
  Group,
  Loader,
  Paper,
  Stack,
  Text,
  Title,
} from '@/components/ui/legacy'
import {
  createRepository,
  deleteRepository,
  errorToUserMessage,
  fetchRepositories,
  fetchSandboxes,
  getToken,
  type Repository,
  type Sandbox,
  syncRepository,
  updateRepository,
} from '../api'
import { RepositoryDocumentsModal } from '../components/RepositoryDocumentsModal'
import {
  buildPayload,
  EMPTY_FORM,
  formFromRepository,
  type FormState,
} from './admin-repositories/form'
import { RepositoriesTable } from './admin-repositories/RepositoriesTable'
import {
  CreateRepositoryModal,
  EditRepositoryModal,
} from './admin-repositories/RepositoryFormModals'

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
      await createRepository(token, buildPayload(form))
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
      await updateRepository(token, editingRepo.id, buildPayload(form, editingRepo))
      setForm(EMPTY_FORM)
      setEditingRepo(null)
      await reload()
    } catch (err) {
      setFormError(errorToUserMessage(err))
    } finally {
      setUpdating(false)
    }
  }

  function closeEdit() {
    setEditingRepo(null)
    setForm(EMPTY_FORM)
    setFormError(null)
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
    if (!window.confirm('Remover este repositório?? A operação dispara remoção do sandbox também.')) {
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
            <RepositoriesTable
              repos={repos}
              busyId={busyId}
              onDocuments={setDocumentsRepo}
              onEdit={openEdit}
              onSync={(repoId) => void handleSync(repoId)}
              onDelete={(repoId) => void handleDelete(repoId)}
            />
          )}
        </Paper>
      </Stack>

      <RepositoryDocumentsModal
        opened={documentsRepo !== null}
        repository={documentsRepo}
        token={getToken() ?? ''}
        onClose={() => setDocumentsRepo(null)}
      />

      <CreateRepositoryModal
        opened={createOpen}
        form={form}
        setForm={setForm}
        formError={formError}
        sandboxOptions={sandboxOptions}
        busy={creating}
        onClose={() => setCreateOpen(false)}
        onSubmit={() => void handleCreate()}
      />

      <EditRepositoryModal
        editingRepo={editingRepo}
        form={form}
        setForm={setForm}
        formError={formError}
        sandboxOptions={sandboxOptions}
        busy={updating}
        onClose={closeEdit}
        onSubmit={() => void handleUpdate()}
      />
    </Container>
  )
}
