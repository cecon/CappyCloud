import { useCallback, useEffect, useState } from 'react'
import {
  ActionIcon,
  Alert,
  Badge,
  Button,
  Container,
  Group,
  Loader,
  Menu,
  Modal,
  Paper,
  Select,
  Stack,
  Table,
  Text,
  TextInput,
  Title,
} from '@/components/ui/legacy'
import {
  IconCopy,
  IconDotsVertical,
  IconPlayerPlay,
  IconPlayerStop,
  IconSettings,
  IconTrash,
} from '@tabler/icons-react'
import {
  bootAdminSandbox,
  cloneAdminSandbox,
  type ContainerStatus,
  createAdminSandbox,
  deleteAdminSandbox,
  errorToUserMessage,
  fetchAdminSandboxes,
  getToken,
  type Sandbox,
  type SandboxRuntime,
  stopAdminSandbox,
} from '../api'
import { SandboxGlobalsDrawer } from '../components/SandboxGlobalsDrawer'
import { ActionsCell, ActionsHeader, RowActionIcon } from '../components/TableActions'

type CreateState = {
  name: string
  runtime: SandboxRuntime
  image: string
  envEntries: { key: string; value: string }[]
}

const EMPTY_CREATE: CreateState = {
  name: '',
  runtime: 'compose',
  image: '',
  envEntries: [{ key: '', value: '' }],
}

const STATUS_COLORS: Record<ContainerStatus, string> = {
  not_created: 'gray',
  starting: 'yellow',
  running: 'blue',
  configuring: 'cyan',
  configured: 'green',
  stopped: 'gray',
  error: 'red',
}

const STATUS_LABELS: Record<ContainerStatus, string> = {
  not_created: 'NÃO CRIADO',
  starting: 'INICIANDO',
  running: 'RODANDO',
  configuring: 'CONFIGURANDO',
  configured: 'CONFIGURADO',
  stopped: 'PARADO',
  error: 'ERRO',
}

function envEntriesToRecord(entries: { key: string; value: string }[]): Record<string, string> {
  const out: Record<string, string> = {}
  for (const { key, value } of entries) {
    const k = key.trim()
    if (k) out[k] = value
  }
  return out
}

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

  const [pendingAction, setPendingAction] = useState<string | null>(null)

  const reload = useCallback(async () => {
    const token = getToken()
    if (!token) return
    try {
      const list = await fetchAdminSandboxes(token)
      setItems(list)
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

  function addEnvRow() {
    setForm({ ...form, envEntries: [...form.envEntries, { key: '', value: '' }] })
  }

  function updateEnvRow(idx: number, key: 'key' | 'value', value: string) {
    const next = form.envEntries.map((row, i) => (i === idx ? { ...row, [key]: value } : row))
    setForm({ ...form, envEntries: next })
  }

  function removeEnvRow(idx: number) {
    setForm({ ...form, envEntries: form.envEntries.filter((_, i) => i !== idx) })
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
            <Table verticalSpacing="sm" highlightOnHover>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Nome</Table.Th>
                  <Table.Th style={{ width: 120 }}>Runtime</Table.Th>
                  <Table.Th>Imagem</Table.Th>
                  <Table.Th style={{ width: 180 }}>Container</Table.Th>
                  <ActionsHeader width={132} />
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {items.map((sb) => {
                  const isPending = pendingAction === sb.id
                  const containerExists = sb.container_status !== 'not_created'
                  const stoppable =
                    sb.container_status === 'running' ||
                    sb.container_status === 'configured' ||
                    sb.container_status === 'configuring' ||
                    sb.container_status === 'starting'
                  return (
                    <Table.Tr key={sb.id}>
                      <Table.Td>
                        <Text fw={600}>{sb.name}</Text>
                        <Text size="xs" c="dimmed">
                          {sb.host}:{sb.grpc_port}/{sb.session_port}
                        </Text>
                      </Table.Td>
                      <Table.Td>
                        <Badge variant="light" color={sb.runtime === 'compose' ? 'blue' : 'grape'}>
                          {sb.runtime.toUpperCase()}
                        </Badge>
                      </Table.Td>
                      <Table.Td>
                        <Text size="sm" style={{ wordBreak: 'break-all' }}>
                          {sb.image || <em style={{ opacity: 0.5 }}>(vazia)</em>}
                        </Text>
                      </Table.Td>
                      <Table.Td>
                        <Badge
                          color={STATUS_COLORS[sb.container_status]}
                          variant={sb.container_status === 'configured' ? 'filled' : 'light'}
                        >
                          {STATUS_LABELS[sb.container_status]}
                        </Badge>
                      </Table.Td>
                      <ActionsCell>
                        <RowActionIcon
                          label="Iniciar/recriar container"
                          color="blue"
                          onClick={() => void handleBoot(sb)}
                          loading={isPending}
                          disabled={isPending}
                        >
                          <IconPlayerPlay size={16} />
                        </RowActionIcon>
                        <RowActionIcon
                          label="Parar container"
                          color="gray"
                          variant="default"
                          onClick={() => void handleStop(sb)}
                          loading={isPending}
                          disabled={isPending || !stoppable}
                        >
                          <IconPlayerStop size={16} />
                        </RowActionIcon>
                        <Menu shadow="md" position="bottom-end">
                          <Menu.Target>
                            <ActionIcon
                              aria-label="Mais ações"
                              title="Mais ações"
                              variant="default"
                              size="lg"
                              disabled={isPending}
                            >
                              <IconDotsVertical size={16} />
                            </ActionIcon>
                          </Menu.Target>
                          <Menu.Dropdown>
                            <Menu.Item
                              leftSection={<IconSettings size={14} />}
                              onClick={() => setGlobalsFor(sb)}
                            >
                              MCPs / Skills / Agents...
                            </Menu.Item>
                            <Menu.Item
                              leftSection={<IconCopy size={14} />}
                              onClick={() => {
                                setCloneFor(sb)
                                setCloneName(`${sb.name}-copy`)
                              }}
                            >
                              Clonar
                            </Menu.Item>
                            <Menu.Item
                              color="red"
                              leftSection={<IconTrash size={14} />}
                              disabled={
                                containerExists &&
                                sb.container_status !== 'stopped' &&
                                sb.container_status !== 'error'
                              }
                              onClick={() => void handleDelete(sb)}
                            >
                              Apagar
                            </Menu.Item>
                          </Menu.Dropdown>
                        </Menu>
                      </ActionsCell>
                    </Table.Tr>
                  )
                })}
              </Table.Tbody>
            </Table>
          )}
        </Paper>
      </Stack>

      {/* Criar */}
      <Modal
        opened={createOpen}
        onClose={() => setCreateOpen(false)}
        title="Nova sandbox"
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
            label="Nome"
            description="Identificador único — vira parte do nome do container Docker."
            placeholder="alpha"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.currentTarget.value })}
            required
          />
          <Select
            label="Runtime"
            description="Compose = dev local. Swarm = produção (ainda em implementação)."
            data={[
              { value: 'compose', label: 'Compose (Docker Desktop, dev)' },
              { value: 'swarm', label: 'Swarm (produção — ainda não implementado)' },
            ]}
            value={form.runtime}
            onChange={(value) => {
              if (value === 'compose' || value === 'swarm') {
                setForm({ ...form, runtime: value })
              }
            }}
            allowDeselect={false}
          />
          <TextInput
            label="Imagem Docker"
            description="Imagem que o adapter usa ao criar o container."
            placeholder="cappycloud/sandbox:latest"
            value={form.image}
            onChange={(e) => setForm({ ...form, image: e.currentTarget.value })}
            required
          />
          <Stack gap={6}>
            <Text size="sm" fw={500}>
              Variáveis de ambiente
            </Text>
            {form.envEntries.map((row, idx) => (
              <Group key={idx} gap="xs">
                <TextInput
                  placeholder="KEY"
                  value={row.key}
                  onChange={(e) => updateEnvRow(idx, 'key', e.currentTarget.value)}
                  style={{ flex: 1 }}
                />
                <TextInput
                  placeholder="valor"
                  value={row.value}
                  onChange={(e) => updateEnvRow(idx, 'value', e.currentTarget.value)}
                  style={{ flex: 2 }}
                />
                <ActionIcon
                  variant="subtle"
                  color="red"
                  onClick={() => removeEnvRow(idx)}
                  disabled={form.envEntries.length === 1}
                >
                  ×
                </ActionIcon>
              </Group>
            ))}
            <Button size="xs" variant="default" onClick={addEnvRow}>
              + adicionar variável
            </Button>
          </Stack>
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

      {/* MCPs do sandbox */}
      <SandboxGlobalsDrawer sandbox={globalsFor} onClose={() => setGlobalsFor(null)} />

      {/* Clonar */}
      <Modal
        opened={cloneFor !== null}
        onClose={() => setCloneFor(null)}
        title={cloneFor ? `Clonar sandbox "${cloneFor.name}"` : 'Clonar sandbox'}
        centered
      >
        <Stack gap="md">
          <Text size="sm" c="dimmed">
            Copia imagem, runtime e variáveis. O container do clone começa em <strong>não criado</strong>.
          </Text>
          <TextInput
            label="Nome do clone"
            value={cloneName}
            onChange={(e) => setCloneName(e.currentTarget.value)}
            required
          />
          <Group justify="flex-end">
            <Button variant="default" onClick={() => setCloneFor(null)} disabled={cloning}>
              Cancelar
            </Button>
            <Button onClick={() => void handleClone()} loading={cloning}>
              Clonar
            </Button>
          </Group>
        </Stack>
      </Modal>
    </Container>
  )
}
