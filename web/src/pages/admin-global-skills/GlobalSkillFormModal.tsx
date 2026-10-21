import type { Dispatch, SetStateAction } from 'react'
import {
  Alert,
  Button,
  Group,
  Modal,
  MultiSelect,
  Stack,
  Switch,
  TextInput,
} from '@/components/ui/legacy'
import { MarkdownEditor } from '../../components/MarkdownEditor'
import type { FormState } from './form'

type GlobalSkillFormModalProps = {
  opened: boolean
  form: FormState
  setForm: Dispatch<SetStateAction<FormState>>
  formError: string | null
  saving: boolean
  sandboxOptions: { value: string; label: string }[]
  onClose: () => void
  onSave: () => void
}

export function GlobalSkillFormModal({
  opened,
  form,
  setForm,
  formError,
  saving,
  sandboxOptions,
  onClose,
  onSave,
}: GlobalSkillFormModalProps) {
  return (
    <Modal
      opened={opened}
      onClose={onClose}
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
        <MarkdownEditor
          label="Conteúdo (markdown)"
          placeholder={'# Skill\nInstruções para o agente.'}
          value={form.content}
          onChange={(content) => setForm({ ...form, content })}
        />
        <Switch
          label="Ativo"
          checked={form.enabled}
          onChange={(e) => setForm({ ...form, enabled: e.currentTarget.checked })}
        />
        <Group justify="flex-end">
          <Button variant="default" onClick={onClose} disabled={saving}>
            Cancelar
          </Button>
          <Button onClick={onSave} loading={saving}>
            {form.id ? 'Salvar' : 'Criar'}
          </Button>
        </Group>
      </Stack>
    </Modal>
  )
}
