import { useCallback, useEffect, useMemo, useState } from 'react'
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
import { EMPTY_FORM, type FormState } from './admin-global-skills/form'
import { GlobalSkillFormModal } from './admin-global-skills/GlobalSkillFormModal'
import { GlobalSkillsTable } from './admin-global-skills/GlobalSkillsTable'

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
    if (!window.confirm(`Apagar skill global "${skill.name}"?? `)) return
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

  const loading = skills === null || sandboxes === null

  return (
    <Container size="lg" py="xl">
      <Stack gap="lg">
        <Group justify="space-between" align="flex-start">
          <Stack gap={4}>
            <Title order={2}>Skills globais</Title>
            <Text c="dimmed" size="sm">
              Catalogo global de skills. Cada skill e adicionada as sandboxes selecionadas e
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
            <GlobalSkillsTable
              skills={skills}
              sandboxById={sandboxById}
              onToggle={(skill) => void handleToggle(skill)}
              onEdit={openEdit}
              onDelete={(skill) => void handleDelete(skill)}
            />
          )}
        </Paper>
      </Stack>

      <GlobalSkillFormModal
        opened={editOpen}
        form={form}
        setForm={setForm}
        formError={formError}
        saving={saving}
        sandboxOptions={sandboxOptions}
        onClose={() => setEditOpen(false)}
        onSave={() => void handleSave()}
      />
    </Container>
  )
}
