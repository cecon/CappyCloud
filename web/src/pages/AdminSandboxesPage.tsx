import { useCallback, useEffect, useState } from 'react'
import { Alert, Button, Container, Group, Loader, Paper, Stack, Text, Title } from '@/components/ui/legacy'
import {
  bootAdminSandbox,
  cloneAdminSandbox,
  createAdminSandbox,
  deleteAdminSandbox,
  errorToUserMessage,
  fetchAdminSandboxes,
  getToken,
  type Sandbox,
  stopAdminSandbox,
} from '../api'
import { SandboxGlobalsDrawer } from '../components/SandboxGlobalsDrawer'
import { SandboxTerminalModal } from '../components/SandboxTerminalModal'
import { useCurrentUser } from '../hooks/useCurrentUser'
import { CloneSandboxModal } from './admin-sandboxes/CloneSandboxModal'
import { type CreateState, EMPTY_CREATE, envEntriesToRecord, STATUS_POLL_MS } from './admin-sandboxes/constants'
import { CreateSandboxModal } from './admin-sandboxes/CreateSandboxModal'
import { SandboxesTable } from './admin-sandboxes/SandboxesTable'

export function AdminSandboxesPage() {
  const [items, setItems] = useState<Sandbox[] | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)

  const [createOpen, setCreateOpen] = useState(false)
  const [form, setForm] = useState<CreateState>(EMPTY_CREATE)
  const [formError, setFormError] = useState<string | null>(null)
  const [creating, setCreating] = useState(false)

  const [cloneFor, setCloneFor] = useState<Sandbox | null>(null)
  const [cloneName, setCloneName] = useState('')
  const [cloning, setCloning] = useState(false)

  const [globalsFor, setGlobalsFor] = useState<Sandbox | null>(null)
  const [globalsTab, setGlobalsTab] = useState<'claude' | 'runtime'>('claude')
  const openGlobals = (sb: Sandbox, tab: 'claude' | 'runtime') => {
    setGlobalsTab(tab)
    setGlobalsFor(sb)
  }
  const [terminalFor, setTerminalFor] = useState<Sandbox | null>(null)
  const currentUser = useCurrentUser()
  // Terminal abre um shell no container: só super admin.
  const canUseTerminal = currentUser.status === 'ready' && currentUser.user.is_super_admin

  const [pendingAction, setPendingAction] = useState<string | null>(null)

  const reload = useCallback(async (options: { silent?: boolean } = {}) => {
    const token = getToken()
    if (!token) return
    try {
      const list = await fetchAdminSandboxes(token)
      setItems(list)
      setLoadError(null)
    } catch (err) {
      if (!options.silent) {
        setLoadError(errorToUserMessage(err))
      }
    }
  }, [])

  useEffect(() => {
    void reload()
  }, [reload])

  useEffect(() => {
    const timer = window.setInterval(() => {
      void reload({ silent: true })
    }, STATUS_POLL_MS)
    return () => window.clearInterval(timer)
  }, [reload])

  async function handleCreate() {
    const token = getToken()
    if (!token) return
    if (!form.name.trim()) {
      setFormError('Nome é obrigatório.')
      return
    }
    if (!form.image.trim()) {
      setFormError('Imagem Docker é obrigatória (para boot).')
      return
    }
    setCreating(true)
    setFormError(null)
    try {
      await createAdminSandbox(token, {
        name: form.name.trim(),
        runtime: form.runtime,
        agent_runtime: form.agentRuntime,
        image: form.image.trim(),
        env_vars: envEntriesToRecord(form.envEntries),
      })
      setForm(EMPTY_CREATE)
      setCreateOpen(false)
      await reload()
    } catch (err) {
      setFormError(errorToUserMessage(err))
    } finally {
      setCreating(false)
    }
  }

  async function handleBoot(sb: Sandbox) {
    const token = getToken()
    if (!token) return
    setPendingAction(sb.id)
    setActionError(null)
    try {
      const updated = await bootAdminSandbox(token, sb.id)
      setItems((prev) =>
        prev ? prev.map((s) => (s.id === updated.id ? updated : s)) : prev,
      )
    } catch (err) {
      setActionError(errorToUserMessage(err))
      // Recarrega — o status pode ter virado "error" no backend:
      await reload()
    } finally {
      setPendingAction(null)
    }
  }

  async function handleStop(sb: Sandbox) {
    const token = getToken()
    if (!token) return
    setPendingAction(sb.id)
    setActionError(null)
    try {
      const updated = await stopAdminSandbox(token, sb.id)
      setItems((prev) =>
        prev ? prev.map((s) => (s.id === updated.id ? updated : s)) : prev,
      )
    } catch (err) {
      setActionError(errorToUserMessage(err))
      await reload()
    } finally {
      setPendingAction(null)
    }
  }

  async function handleDelete(sb: Sandbox) {
    if (!window.confirm(`Apagar sandbox "${sb.name}"?? Esta ação não pode ser desfeita.`)) {
      return
    }
    const token = getToken()
    if (!token) return
    setPendingAction(sb.id)
    setActionError(null)
    try {
      await deleteAdminSandbox(token, sb.id)
      setItems((prev) => (prev ? prev.filter((s) => s.id !== sb.id) : prev))
    } catch (err) {
      setActionError(errorToUserMessage(err))
    } finally {
      setPendingAction(null)
    }
  }

  async function handleClone() {
    if (!cloneFor) return
    const token = getToken()
    if (!token) return
    if (!cloneName.trim()) return
    setCloning(true)
    setActionError(null)
    try {
      const created = await cloneAdminSandbox(token, cloneFor.id, cloneName.trim())
      setItems((prev) => (prev ? [...prev, created] : prev))
      setCloneFor(null)
      setCloneName('')
    } catch (err) {
      setActionError(errorToUserMessage(err))
    } finally {
      setCloning(false)
    }
  }

  function applyUpdatedSandbox(updated: Sandbox) {
    setItems((prev) => (prev ? prev.map((s) => (s.id === updated.id ? updated : s)) : prev))
    setGlobalsFor((current) => (current?.id === updated.id ? updated : current))
  }

  return (
    <Container size="xl" py="xl">
      <Stack gap="lg">
        <Group justify="space-between" align="flex-end">
          <Stack gap={4}>
            <Title order={2}>Sandboxes</Title>
            <Text c="dimmed" size="sm">
              Cadastro de containers openclaude. Cada sandbox é 1 container compartilhado por
              vários usuários (ADR-004).
            </Text>
          </Stack>
          <Button
            onClick={() => {
              setForm(EMPTY_CREATE)
              setFormError(null)
              setCreateOpen(true)
            }}
          >
            Nova sandbox
          </Button>
        </Group>

        {actionError && (
          <Alert color="red" title="Falha na operação" withCloseButton onClose={() => setActionError(null)}>
            {actionError}
          </Alert>
        )}

        <Paper withBorder p="md" radius="md">
          {loadError ? (
            <Alert color="red" title="Não foi possível carregar sandboxes">
              {loadError}
            </Alert>
          ) : items === null ? (
            <Group justify="center" py="xl">
              <Loader />
            </Group>
          ) : items.length === 0 ? (
            <Text c="dimmed" ta="center" py="xl">
              Nenhuma sandbox cadastrada. Use “Nova sandbox” para criar a primeira.
            </Text>
          ) : (
            <SandboxesTable
              items={items}
              pendingAction={pendingAction}
              canUseTerminal={canUseTerminal}
              onBoot={(sb) => void handleBoot(sb)}
              onStop={(sb) => void handleStop(sb)}
              onDelete={(sb) => void handleDelete(sb)}
              onOpenGlobals={openGlobals}
              onClone={(sb) => {
                setCloneFor(sb)
                setCloneName(`${sb.name}-copy`)
              }}
              onTerminal={setTerminalFor}
            />
          )}
        </Paper>
      </Stack>

      {/* Criar */}
      <CreateSandboxModal
        opened={createOpen}
        form={form}
        setForm={setForm}
        formError={formError}
        creating={creating}
        onClose={() => setCreateOpen(false)}
        onCreate={() => void handleCreate()}
      />

      {/* MCPs do sandbox */}
      <SandboxGlobalsDrawer
        sandbox={globalsFor}
        initialTab={globalsTab}
        onClose={() => setGlobalsFor(null)}
        onUpdated={applyUpdatedSandbox}
      />

      {terminalFor && <SandboxTerminalModal sandbox={terminalFor} onClose={() => setTerminalFor(null)} />}

      {/* Clonar */}
      <CloneSandboxModal
        cloneFor={cloneFor}
        cloneName={cloneName}
        cloning={cloning}
        onNameChange={setCloneName}
        onClose={() => setCloneFor(null)}
        onClone={() => void handleClone()}
      />
    </Container>
  )
}
