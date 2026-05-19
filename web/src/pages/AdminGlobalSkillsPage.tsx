import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Alert,
  Badge,
  Button,
  Container,
  Group,
  Loader,
  Modal,
  MultiSelect,
  Paper,
  Stack,
  Switch,
  Table,
  Text,
  Textarea,
  TextInput,
  Title,
} from '@mantine/core'
import { IconPencil, IconTrash } from '@tabler/icons-react'
import {
  createGlobalSkill,
  deleteGlobalSkill,
  errorToUserMessage,
  fetchAdminSandboxes,
  fetchGlobalSkills,
  getToken,
  type GlobalSkill,
  type Sandbox,
  updateGlobalSkill,
} from '../api'
import { ActionsCell, ActionsHeader, RowActionIcon } from '../components/TableActions'

type FormState = {
  id: string | null
  name: string
  description: string
  content: string
  enabled: boolean
  sandbox_ids: string[]
}

const EMPTY_FORM: FormState = {
  id: null,
  name: '',
  description: '',
  content: '',
  enabled: true,
  sandbox_ids: [],
}

export function AdminGlobalSkillsPage() {
  const [skills, setSkills] = useState<GlobalSkill[] | null>(null)
  const [sandboxes, setSandboxes] = useState<Sandbox[] | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [editOpen, setEditOpen] = useState(false)
  const [form, setForm] = useState<FormState>(EMPTY_FORM)
  const [formError, setFormError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  const load = useCallback(async () => {
    const token = getToken()
    if (!token) return
    setLoadError(null)
    try {
      const [sandboxList, skillList] = await Promise.all([
        fetchAdminSandboxes(token),
        fetchGlobalSkills(token),
      ])
      setSandboxes(sandboxList)
      setSkills(skillList)
    } catch (err) {
      setLoadError(errorToUserMessage(err))
      setSandboxes([])
      setSkills([])
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const sandboxById = useMemo(() => {
    const map = new Map<string, Sandbox>()
    for (const sandbox of sandboxes ?? []) {
      map.set(sandbox.id, sandbox)
    }
    return map
  }, [sandboxes])

  const sandboxOptions = useMemo(
    () =>
      (sandboxes ?? []).map((sandbox) => ({
        value: sandbox.id,
        label: sandbox.name,
      })),
    [sandboxes],
  )

  function openCreate() {
    setForm(EMPTY_FORM)
    setFormError(null)
    setEditOpen(true)
  }

  function openEdit(skill: GlobalSkill) {
    setForm({
      id: skill.id,
      name: skill.name,
      description: skill.description,
      content: skill.content,
      enabled: skill.enabled,
      sandbox_ids: skill.sandbox_ids,
    })
    setFormError(null)
    setEditOpen(true)
  }

  function payloadFrom(skill: GlobalSkill) {
    return {
      name: skill.name,
      description: skill.description,
      content: skill.content,
      enabled: skill.enabled,
      sandbox_ids: skill.sandbox_ids,
    }
  }

  async function handleSave() {
    const token = getToken()
    if (!token) return
    if (!form.name.trim()) {
      setFormError('Nome é obrigatório.')
      return
    }
    if (form.sandbox_ids.length === 0) {
      setFormError('Selecione ao menos uma sandbox.')
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
        sandbox_ids: form.sandbox_ids,
      }
      const saved = form.id
        ? await updateGlobalSkill(token, form.id, payload)
        : await createGlobalSkill(token, payload)
      setSkills((current) => {
        const list = current ?? []
        if (!form.id) return [...list, saved]
        return list.map((skill) => (skill.id === saved.id ? saved : skill))
      })
      setEditOpen(false)
    } catch (err) {
      setFormError(errorToUserMessage(err))
    } finally {
      setSaving(false)
    }
  }

  async function handleToggle(skill: GlobalSkill) {
    const token = getToken()
    if (!token) return
    setActionError(null)
    try {
      const updated = await updateGlobalSkill(token, skill.id, {
        ...payloadFrom(skill),
        enabled: !skill.enabled,
      })
      setSkills((current) =>
        current ? current.map((item) => (item.id === updated.id ? updated : item)) : current,
      )
    } catch (err) {
      setActionError(errorToUserMessage(err))
    }
  }

  async function handleDelete(skill: GlobalSkill) {
    if (!window.confirm(`Apagar skill global "${skill.name}"?`)) return
    const token = getToken()
    if (!token) return
    setActionError(null)
    try {
      await deleteGlobalSkill(token, skill.id)
      setSkills((current) => (current ? current.filter((item) => item.id !== skill.id) : current))
    } catch (err) {
      setActionError(errorToUserMessage(err))
    }
  }

  function renderAssignedSandboxes(skill: GlobalSkill) {
    if (skill.sandbox_ids.length === 0) {
      return (
        <Text size="sm" c="dimmed" fs="italic">
          Nenhuma
        </Text>
      )
    }
    return (
      <Group gap={6}>
        {skill.sandbox_ids.map((sandboxId) => (
          <Badge key={sandboxId} variant="light" color="blue">
            {sandboxById.get(sandboxId)?.name ?? sandboxId.slice(0, 8)}
          </Badge>
        ))}
      </Group>
    )
  }

  const loading = skills === null || sandboxes === null

  return (
    <Container size="lg" py="xl">
      <Stack gap="lg">
        <Group justify="space-between" align="flex-start">
          <Stack gap={4}>
            <Title order={2}>Skills globais</Title>
            <Text c="dimmed" size="sm">
              Catálogo global de skills. Cada skill é adicionada às sandboxes selecionadas e
              escrita em ~/.claude/skills no boot.
            </Text>
          </Stack>
          <Button onClick={openCreate} disabled={loading || sandboxOptions.length === 0}>
            Nova skill
          </Button>
        </Group>

        {loadError && (
          <Alert color="red" title="Não foi possível carregar skills globais">
            {loadError}
          </Alert>
        )}
        {actionError && (
          <Alert color="red" withCloseButton onClose={() => setActionError(null)}>
            {actionError}
          </Alert>
        )}

        <Paper withBorder radius="md" p="md">
          {loading ? (
            <Group justify="center" py="xl">
              <Loader />
            </Group>
          ) : sandboxOptions.length === 0 ? (
            <Text c="dimmed" ta="center" py="xl">
              Cadastre uma sandbox antes de adicionar skills globais.
            </Text>
          ) : skills.length === 0 ? (
            <Text c="dimmed" ta="center" py="xl">
              Nenhuma skill global cadastrada.
            </Text>
          ) : (
            <Table verticalSpacing="sm" highlightOnHover>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Nome</Table.Th>
                  <Table.Th>Descrição</Table.Th>
                  <Table.Th>Sandboxes</Table.Th>
                  <Table.Th w={90}>Ativo</Table.Th>
                  <ActionsHeader width={110} />
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {skills.map((skill) => (
                  <Table.Tr key={skill.id}>
                    <Table.Td>
                      <Text fw={600}>{skill.name}</Text>
                    </Table.Td>
                    <Table.Td>
                      <Text size="sm" lineClamp={2}>
                        {skill.description || (
                          <Text span c="dimmed" fs="italic">
                            sem descrição
                          </Text>
                        )}
                      </Text>
                    </Table.Td>
                    <Table.Td>{renderAssignedSandboxes(skill)}</Table.Td>
                    <Table.Td>
                      <Switch
                        checked={skill.enabled}
                        onChange={() => void handleToggle(skill)}
                        size="xs"
                        aria-label={`Ativar ${skill.name}`}
                      />
                    </Table.Td>
                    <ActionsCell>
                      <RowActionIcon label="Editar" onClick={() => openEdit(skill)}>
                        <IconPencil size={16} />
                      </RowActionIcon>
                      <RowActionIcon
                        label="Apagar"
                        color="red"
                        onClick={() => void handleDelete(skill)}
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

      <Modal
        opened={editOpen}
        onClose={() => setEditOpen(false)}
        title={form.id ? `Editar skill "${form.name}"` : 'Nova skill global'}
        centered
        size="lg"
      >
        <Stack gap="md">
          {formError && <Alert color="red">{formError}</Alert>}
          <TextInput
            label="Nome (slug)"
            placeholder="naming-conventions"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.currentTarget.value })}
            required
          />
          <TextInput
            label="Descrição curta"
            placeholder="Convenções do time para esta sandbox."
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.currentTarget.value })}
          />
          <MultiSelect
            label="Adicionar nas sandboxes"
            data={sandboxOptions}
            value={form.sandbox_ids}
            onChange={(value) => setForm({ ...form, sandbox_ids: value })}
            searchable
            required
            placeholder="Selecione uma ou mais sandboxes"
          />
          <Textarea
            label="Conteúdo (markdown)"
            placeholder="# Skill&#10;Instruções para o agente."
            value={form.content}
            onChange={(e) => setForm({ ...form, content: e.currentTarget.value })}
            autosize
            minRows={8}
            maxRows={20}
            styles={{ input: { fontFamily: 'monospace' } }}
          />
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
    </Container>
  )
}
