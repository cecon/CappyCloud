import { useCallback, useEffect, useState } from 'react'
import {
  ActionIcon,
  Alert,
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
  createSandboxSkill,
  deleteSandboxSkill,
  errorToUserMessage,
  fetchSandboxSkills,
  getToken,
  type Sandbox,
  type SandboxSkill,
  updateSandboxSkill,
} from '../../api'

type Props = {
  sandbox: Sandbox
  canManage?: boolean
}

type FormState = {
  id: string | null
  name: string
  description: string
  content: string
  enabled: boolean
}

const EMPTY_FORM: FormState = {
  id: null,
  name: '',
  description: '',
  content: '',
  enabled: true,
}

export function SandboxSkillsPanel({ sandbox, canManage = true }: Props) {
  const [items, setItems] = useState<SandboxSkill[] | null>(null)
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
      const list = await fetchSandboxSkills(token, sandbox.id)
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

  function openEdit(skill: SandboxSkill) {
    setForm({
      id: skill.id,
      name: skill.name,
      description: skill.description,
      content: skill.content,
      enabled: skill.enabled,
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
        content: form.content,
        enabled: form.enabled,
      }
      if (form.id) {
        await updateSandboxSkill(token, sandbox.id, form.id, payload)
      } else {
        await createSandboxSkill(token, sandbox.id, payload)
      }
      setEditOpen(false)
      await reload()
    } catch (err) {
      setFormError(errorToUserMessage(err))
    } finally {
      setSaving(false)
    }
  }

  async function handleDelete(skill: SandboxSkill) {
    if (!window.confirm(`Apagar skill "${skill.name}"?? `)) return
    const token = getToken()
    if (!token) return
    try {
      await deleteSandboxSkill(token, sandbox.id, skill.id)
      setItems((prev) => (prev ? prev.filter((s) => s.id !== skill.id) : prev))
    } catch (err) {
      setActionError(errorToUserMessage(err))
    }
  }

  async function handleToggle(skill: SandboxSkill) {
    const token = getToken()
    if (!token) return
    try {
      const updated = await updateSandboxSkill(token, sandbox.id, skill.id, {
        name: skill.name,
        description: skill.description,
        content: skill.content,
        enabled: !skill.enabled,
      })
      setItems((prev) => (prev ? prev.map((s) => (s.id === updated.id ? updated : s)) : prev))
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
            : `${items.length} skill${items.length === 1 ? '' : 's'} · ~/.claude/skills/<name>/SKILL.md`}
        </Text>
        {items !== null && (
          <Text size="xs" c="dimmed" ff="monospace">
            skill://sandbox/{sandbox.id}/&lt;name&gt;
          </Text>
        )}
        {canManage && (
          <Button size="xs" onClick={openCreate}>
            + Nova skill
          </Button>
        )}
      </Group>
      {!canManage && (
        <Alert color="yellow" title="Catálogo global">
          Esta aba mostra as skills atribuídas a esta sandbox. Criação, edição, ativação e
          remoção são feitas em Skills globais.
        </Alert>
      )}
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
          Nenhuma skill configurada.
        </Text>
      ) : (
        <Table verticalSpacing="xs" highlightOnHover>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Nome</Table.Th>
              <Table.Th>Descrição</Table.Th>
              <Table.Th style={{ width: 90 }}>Ativo</Table.Th>
              {canManage && <Table.Th style={{ width: 100 }}>Ações</Table.Th>}
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {items.map((skill) => (
              <Table.Tr key={skill.id}>
                <Table.Td>
                  <Text fw={600}>{skill.name}</Text>
                </Table.Td>
                <Table.Td>
                  <Text size="sm" lineClamp={2}>
                    {skill.description || <em style={{ opacity: 0.5 }}>(sem descrição)</em>}
                  </Text>
                </Table.Td>
                <Table.Td>
                  <Switch
                    checked={skill.enabled}
                    onChange={() => void handleToggle(skill)}
                    size="xs"
                    disabled={!canManage}
                  />
                </Table.Td>
                {canManage && (
                  <Table.Td>
                    <Group gap={4}>
                      <ActionIcon variant="subtle" onClick={() => openEdit(skill)} title="Editar">
                        ✎
                      </ActionIcon>
                      <ActionIcon
                        variant="subtle"
                        color="red"
                        onClick={() => void handleDelete(skill)}
                        title="Apagar"
                      >
                        ×
                      </ActionIcon>
                    </Group>
                  </Table.Td>
                )}
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}

      <Modal
        opened={editOpen}
        onClose={() => setEditOpen(false)}
        title={form.id ? `Editar skill "${form.name}"` : 'Nova skill'}
        centered
        size="lg"
      >
        <Stack gap="md">
          {formError && <Alert color="red">{formError}</Alert>}
          <TextInput
            label="Nome (slug)"
            description="Vira o nome da pasta em ~/.claude/skills/<name>/"
            placeholder="naming-conventions"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.currentTarget.value })}
            required
          />
          <TextInput
            label="Descrição curta"
            placeholder="Convenções de nomenclatura do CappyCloud."
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.currentTarget.value })}
          />
          <Textarea
            label="Conteúdo (markdown)"
            description="Corpo do arquivo SKILL.md que o openclaude vai ler."
            placeholder="# Naming&#10;- Python: snake_case&#10;- TS: camelCase"
            value={form.content}
            onChange={(e) => setForm({ ...form, content: e.currentTarget.value })}
            autosize
            minRows={6}
            maxRows={20}
            styles={{ input: { fontFamily: 'monospace' } }}
          />
          <Switch
            label="Ativo (entra em ~/.claude/skills/ no próximo boot)"
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
