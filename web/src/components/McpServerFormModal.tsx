import { Alert, Button, Group, Modal, Select, Stack, Switch, TextInput } from '@/components/ui/legacy'

export type McpServerFormState = {
  name: string
  repository_id: string
  enabled: boolean
}

type Props = {
  opened: boolean
  editing: boolean
  form: McpServerFormState
  repoOptions: Array<{ value: string; label: string }>
  formError: string | null
  saving: boolean
  onClose(): void
  onSave(): void
  onChange(form: McpServerFormState): void
}

export function McpServerFormModal({
  opened,
  editing,
  form,
  repoOptions,
  formError,
  saving,
  onClose,
  onSave,
  onChange,
}: Props) {
  return (
    <Modal
      opened={opened}
      onClose={onClose}
      title={editing ? 'Editar MCP server' : 'Novo MCP server'}
      centered
    >
      <Stack gap="md">
        {formError && <Alert color="red">{formError}</Alert>}
        <TextInput
          label="Nome"
          value={form.name}
          onChange={(event) => onChange({ ...form, name: event.currentTarget.value })}
          placeholder="Claude repositório"
        />
        <Select
          label="Repositório"
          data={repoOptions}
          value={form.repository_id || null}
          onChange={(value) => onChange({ ...form, repository_id: value ?? '' })}
          searchable
        />
        <Switch
          label="Ativo"
          checked={form.enabled}
          onChange={(event) => onChange({ ...form, enabled: event.currentTarget.checked })}
        />
        <Group justify="flex-end">
          <Button variant="subtle" onClick={onClose}>
            Cancelar
          </Button>
          <Button loading={saving} onClick={onSave}>
            Salvar
          </Button>
        </Group>
      </Stack>
    </Modal>
  )
}
