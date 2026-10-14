import { useCallback, useEffect, useState } from 'react'
import {
  ActionIcon,
  Alert,
  Badge,
  Button,
  Group,
  Loader,
  Modal,
  Stack,
  Switch,
  Table,
  Text,
  Textarea,
  TextInput,
} from '@/components/ui/legacy'
import {
  createSandboxMcp,
  deleteSandboxMcp,
  errorToUserMessage,
  fetchSandboxMcps,
  getToken,
  type McpServer,
  type Sandbox,
  updateSandboxMcp,
} from '../../api'
import { EMPTY_FORM, envEntriesToRecord, envRecordToEntries, parseArgs, type FormState } from './mcps/form'
import { McpEnvEditor } from './mcps/McpEnvEditor'

type Props = { sandbox: Sandbox }

export function SandboxMcpsPanel({ sandbox }: Props) {
  const [items, setItems] = useState<McpServer[] | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [editOpen, setEditOpen] = useState(false)
  const [form, setForm] = useState<FormState>(EMPTY_FORM)
  const [formError, setFormError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  const reload = useCallback(async () => {
    const token = getToken()
    if (!token) return
    try {
      const list = await fetchSandboxMcps(token, sandbox.id)
      setItems(list)
      setLoadError(null)
    } catch (err) {
      setLoadError(errorToUserMessage(err))
    }
  }, [sandbox.id])

  useEffect(() => {
    setItems(null)
    void reload()
  }, [reload])

  function openCreate() {
    setForm(EMPTY_FORM)
    setFormError(null)
    setEditOpen(true)
  }

  function openEdit(mcp: McpServer) {
    setForm({
      id: mcp.id,
      name: mcp.name,
      command: mcp.command,
      args: mcp.args.join('\n'),
      envEntries: envRecordToEntries(mcp.env),
      enabled: mcp.enabled,
    })
    setFormError(null)
    setEditOpen(true)
  }

  async function handleSave() {
    const token = getToken()
    if (!token) return
    if (!form.name.trim()) {
      setFormError('Nome é obrigatório.')
      return
    }
    if (!form.command.trim()) {
      setFormError('Comando é obrigatório.')
      return
    }
    setSaving(true)
    setFormError(null)
    try {
      const payload = {
        name: form.name.trim(),
        command: form.command.trim(),
        args: parseArgs(form.args),
        env: envEntriesToRecord(form.envEntries),
        enabled: form.enabled,
      }
      if (form.id) {
        await updateSandboxMcp(token, sandbox.id, form.id, payload)
      } else {
        await createSandboxMcp(token, sandbox.id, payload)
      }
      setEditOpen(false)
      await reload()
    } catch (err) {
      setFormError(errorToUserMessage(err))
    } finally {
      setSaving(false)
    }
  }

  async function handleDelete(mcp: McpServer) {
    if (!window.confirm(`Apagar MCP "${mcp.name}"?? `)) return
    const token = getToken()
    if (!token) return
    try {
      await deleteSandboxMcp(token, sandbox.id, mcp.id)
      setItems((prev) => (prev ? prev.filter((m) => m.id !== mcp.id) : prev))
    } catch (err) {
      setActionError(errorToUserMessage(err))
    }
  }

  async function handleToggle(mcp: McpServer) {
    const token = getToken()
    if (!token) return
    try {
      const updated = await updateSandboxMcp(token, sandbox.id, mcp.id, {
        name: mcp.name,
        command: mcp.command,
        args: mcp.args,
        env: mcp.env,
        enabled: !mcp.enabled,
      })
      setItems((prev) => (prev ? prev.map((m) => (m.id === updated.id ? updated : m)) : prev))
    } catch (err) {
      setActionError(errorToUserMessage(err))
    }
  }

  return (
    <Stack gap="md">
      <Group justify="space-between">
        <Text size="sm" c="dimmed">
          {items === null ? 'Carregando...' : `${items.length} MCP${items.length === 1 ? '' : 's'}`}
        </Text>
        <Button size="xs" onClick={openCreate}>
          + Novo MCP
        </Button>
      </Group>
      {loadError && <Alert color="red">{loadError}</Alert>}
      {actionError && (
        <Alert color="red" withCloseButton onClose={() => setActionError(null)}>
          {actionError}
        </Alert>
      )}
      {items === null ? (
        <Group justify="center" py="lg">
          <Loader size="sm" />
        </Group>
      ) : items.length === 0 ? (
        <Text c="dimmed" ta="center" py="md">
          Nenhum MCP configurado.
        </Text>
      ) : (
        <Table verticalSpacing="xs" highlightOnHover>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Nome</Table.Th>
              <Table.Th>Comando</Table.Th>
              <Table.Th style={{ width: 90 }}>Ativo</Table.Th>
              <Table.Th style={{ width: 100 }}>Ações</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {items.map((mcp) => (
              <Table.Tr key={mcp.id}>
                <Table.Td>
                  <Text fw={600}>{mcp.name}</Text>
                  {mcp.args.length > 0 && (
                    <Text size="xs" c="dimmed" style={{ wordBreak: 'break-all' }}>
                      {mcp.args.join(' ')}
                    </Text>
                  )}
                </Table.Td>
                <Table.Td>
                  <Text size="sm">{mcp.command}</Text>
                  {Object.keys(mcp.env).length > 0 && (
                    <Badge size="xs" variant="light" color="gray">
                      {Object.keys(mcp.env).length} env
                    </Badge>
                  )}
                </Table.Td>
                <Table.Td>
                  <Switch checked={mcp.enabled} onChange={() => void handleToggle(mcp)} size="xs" />
                </Table.Td>
                <Table.Td>
                  <Group gap={4}>
                    <ActionIcon variant="subtle" onClick={() => openEdit(mcp)} title="Editar">
                      ✎
                    </ActionIcon>
                    <ActionIcon
                      variant="subtle"
                      color="red"
                      onClick={() => void handleDelete(mcp)}
                      title="Apagar"
                    >
                      ×
                    </ActionIcon>
                  </Group>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}

      <Modal
        opened={editOpen}
        onClose={() => setEditOpen(false)}
        title={form.id ? `Editar MCP "${form.name}"` : 'Novo MCP'}
        centered
        size="lg"
      >
        <Stack gap="md">
          {formError && <Alert color="red">{formError}</Alert>}
          <TextInput
            label="Nome"
            description="Chave em mcpServers do settings.json. Único por sandbox."
            placeholder="github"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.currentTarget.value })}
            required
          />
          <TextInput
            label="Comando"
            description="Executável que lança o servidor MCP."
            placeholder="npx"
            value={form.command}
            onChange={(e) => setForm({ ...form, command: e.currentTarget.value })}
            required
          />
          <Textarea
            label="Argumentos"
            description="Um argumento por linha."
            placeholder="-y&#10;@modelcontextprotocol/server-github"
            value={form.args}
            onChange={(e) => setForm({ ...form, args: e.currentTarget.value })}
            autosize
            minRows={3}
          />
          <McpEnvEditor form={form} setForm={setForm} />
          <Switch
            label="Ativo"
            checked={form.enabled}
            onChange={(e) => setForm({ ...form, enabled: e.currentTarget.checked })}
          />
          <Group justify="flex-end">
            <Button variant="default" onClick={() => setEditOpen(false)} disabled={saving}>
              Cancelar
            </Button>
            <Button onClick={() => void handleSave()} loading={saving}>
              {form.id ? 'Salvar' : 'Criar'}
            </Button>
          </Group>
        </Stack>
      </Modal>
    </Stack>
  )
}
