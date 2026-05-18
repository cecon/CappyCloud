import { useCallback, useEffect, useState } from 'react'
import {
  ActionIcon,
  Alert,
  Badge,
  Button,
  Group,
  Loader,
  Modal,
  PasswordInput,
  Stack,
  Switch,
  Table,
  Text,
  Textarea,
  TextInput,
} from '@mantine/core'
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

type Props = { sandbox: Sandbox }

type FormState = {
  id: string | null
  name: string
  command: string
  args: string
  envEntries: { key: string; value: string }[]
  enabled: boolean
}

const EMPTY_FORM: FormState = {
  id: null,
  name: '',
  command: '',
  args: '',
  envEntries: [{ key: '', value: '' }],
  enabled: true,
}

function envEntriesToRecord(entries: { key: string; value: string }[]): Record<string, string> {
  const out: Record<string, string> = {}
  for (const { key, value } of entries) {
    const k = key.trim()
    if (k) out[k] = value
  }
  return out
}

function envRecordToEntries(env: Record<string, string>): { key: string; value: string }[] {
  const items = Object.entries(env).map(([key, value]) => ({ key, value }))
  return items.length === 0 ? [{ key: '', value: '' }] : items
}

function parseArgs(text: string): string[] {
  return text
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
}

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
    if (!window.confirm(`Apagar MCP "${mcp.name}"?`)) return
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
          <Stack gap={6}>
            <Text size="sm" fw={500}>
              Variáveis de ambiente
            </Text>
            {form.envEntries.map((row, idx) => (
              <Group key={idx} gap="xs">
                <TextInput
                  placeholder="KEY"
                  value={row.key}
                  onChange={(e) =>
                    setForm({
                      ...form,
                      envEntries: form.envEntries.map((r, i) =>
                        i === idx ? { ...r, key: e.currentTarget.value } : r,
                      ),
                    })
                  }
                  style={{ flex: 1 }}
                />
                <PasswordInput
                  placeholder="valor"
                  value={row.value}
                  onChange={(e) =>
                    setForm({
                      ...form,
                      envEntries: form.envEntries.map((r, i) =>
                        i === idx ? { ...r, value: e.currentTarget.value } : r,
                      ),
                    })
                  }
                  style={{ flex: 2 }}
                />
                <ActionIcon
                  variant="subtle"
                  color="red"
                  onClick={() =>
                    setForm({
                      ...form,
                      envEntries: form.envEntries.filter((_, i) => i !== idx),
                    })
                  }
                  disabled={form.envEntries.length === 1}
                >
                  ×
                </ActionIcon>
              </Group>
            ))}
            <Button
              size="xs"
              variant="default"
              onClick={() =>
                setForm({ ...form, envEntries: [...form.envEntries, { key: '', value: '' }] })
              }
            >
              + adicionar variável
            </Button>
          </Stack>
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
