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
} from '@mantine/core'
import {
  createSandboxAgent,
  deleteSandboxAgent,
  errorToUserMessage,
  fetchSandboxAgents,
  getToken,
  type Sandbox,
  type SandboxAgent,
  updateSandboxAgent,
} from '../../api'

type Props = { sandbox: Sandbox }

type FormState = {
  id: string | null
  name: string
  description: string
  system_prompt: string
  model: string
  tools: string
  enabled: boolean
}

const EMPTY_FORM: FormState = {
  id: null,
  name: '',
  description: '',
  system_prompt: '',
  model: '',
  tools: '',
  enabled: true,
}

function parseTools(text: string): string[] {
  return text
    .split(/[,\n]/)
    .map((t) => t.trim())
    .filter(Boolean)
}

export function SandboxAgentsPanel({ sandbox }: Props) {
  const [items, setItems] = useState<SandboxAgent[] | null>(null)
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
      const list = await fetchSandboxAgents(token, sandbox.id)
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

  function openEdit(agent: SandboxAgent) {
    setForm({
      id: agent.id,
      name: agent.name,
      description: agent.description,
      system_prompt: agent.system_prompt,
      model: agent.model,
      tools: agent.tools.join(', '),
      enabled: agent.enabled,
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
    setSaving(true)
    setFormError(null)
    try {
      const payload = {
        name: form.name.trim(),
        description: form.description,
        system_prompt: form.system_prompt,
        model: form.model.trim(),
        tools: parseTools(form.tools),
        enabled: form.enabled,
      }
      if (form.id) {
        await updateSandboxAgent(token, sandbox.id, form.id, payload)
      } else {
        await createSandboxAgent(token, sandbox.id, payload)
      }
      setEditOpen(false)
      await reload()
    } catch (err) {
      setFormError(errorToUserMessage(err))
    } finally {
      setSaving(false)
    }
  }

  async function handleDelete(agent: SandboxAgent) {
    if (!window.confirm(`Apagar subagent "${agent.name}"?`)) return
    const token = getToken()
    if (!token) return
    try {
      await deleteSandboxAgent(token, sandbox.id, agent.id)
      setItems((prev) => (prev ? prev.filter((a) => a.id !== agent.id) : prev))
    } catch (err) {
      setActionError(errorToUserMessage(err))
    }
  }

  async function handleToggle(agent: SandboxAgent) {
    const token = getToken()
    if (!token) return
    try {
      const updated = await updateSandboxAgent(token, sandbox.id, agent.id, {
        name: agent.name,
        description: agent.description,
        system_prompt: agent.system_prompt,
        model: agent.model,
        tools: agent.tools,
        enabled: !agent.enabled,
      })
      setItems((prev) => (prev ? prev.map((a) => (a.id === updated.id ? updated : a)) : prev))
    } catch (err) {
      setActionError(errorToUserMessage(err))
    }
  }

  return (
    <Stack gap="md">
      <Group justify="space-between">
        <Text size="sm" c="dimmed">
          {items === null
            ? 'Carregando...'
            : `${items.length} subagent${items.length === 1 ? '' : 's'} · ~/.claude/agents/<name>.md`}
        </Text>
        <Button size="xs" onClick={openCreate}>
          + Novo subagent
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
          Nenhum subagent configurado.
        </Text>
      ) : (
        <Table verticalSpacing="xs" highlightOnHover>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Nome</Table.Th>
              <Table.Th>Modelo / tools</Table.Th>
              <Table.Th style={{ width: 90 }}>Ativo</Table.Th>
              <Table.Th style={{ width: 100 }}>Ações</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {items.map((agent) => (
              <Table.Tr key={agent.id}>
                <Table.Td>
                  <Text fw={600}>{agent.name}</Text>
                  <Text size="xs" c="dimmed" lineClamp={1}>
                    {agent.description}
                  </Text>
                </Table.Td>
                <Table.Td>
                  {agent.model && (
                    <Badge size="xs" variant="light" color="blue">
                      {agent.model}
                    </Badge>
                  )}
                  {agent.tools.length > 0 && (
                    <Text size="xs" c="dimmed" mt={2}>
                      {agent.tools.join(', ')}
                    </Text>
                  )}
                </Table.Td>
                <Table.Td>
                  <Switch checked={agent.enabled} onChange={() => void handleToggle(agent)} size="xs" />
                </Table.Td>
                <Table.Td>
                  <Group gap={4}>
                    <ActionIcon variant="subtle" onClick={() => openEdit(agent)} title="Editar">
                      ✎
                    </ActionIcon>
                    <ActionIcon
                      variant="subtle"
                      color="red"
                      onClick={() => void handleDelete(agent)}
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
        title={form.id ? `Editar subagent "${form.name}"` : 'Novo subagent'}
        centered
        size="lg"
      >
        <Stack gap="md">
          {formError && <Alert color="red">{formError}</Alert>}
          <TextInput
            label="Nome (slug)"
            description="Vira o nome do arquivo em ~/.claude/agents/<name>.md"
            placeholder="reviewer"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.currentTarget.value })}
            required
          />
          <TextInput
            label="Descrição curta"
            placeholder="Revisor crítico de PRs."
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.currentTarget.value })}
          />
          <Group grow>
            <TextInput
              label="Modelo (opcional)"
              description="ex.: claude-sonnet-4-6"
              placeholder=""
              value={form.model}
              onChange={(e) => setForm({ ...form, model: e.currentTarget.value })}
            />
            <TextInput
              label="Tools (vírgula ou linha)"
              description="ex.: Read, Grep, Bash"
              placeholder="Read, Grep"
              value={form.tools}
              onChange={(e) => setForm({ ...form, tools: e.currentTarget.value })}
            />
          </Group>
          <Textarea
            label="System prompt"
            description="Corpo do arquivo .md, abaixo do frontmatter."
            placeholder="Você é um revisor crítico de código..."
            value={form.system_prompt}
            onChange={(e) => setForm({ ...form, system_prompt: e.currentTarget.value })}
            autosize
            minRows={6}
            maxRows={20}
            styles={{ input: { fontFamily: 'monospace' } }}
          />
          <Switch
            label="Ativo (entra em ~/.claude/agents/ no próximo boot)"
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
