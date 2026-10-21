import {
  ActionIcon,
  Alert,
  Button,
  Group,
  Modal,
  Select,
  Stack,
  Text,
  TextInput,
} from '@/components/ui/legacy'
import type { CreateState } from './constants'

type Props = {
  opened: boolean
  form: CreateState
  setForm: (form: CreateState) => void
  formError: string | null
  creating: boolean
  onClose: () => void
  onCreate: () => void
}

export function CreateSandboxModal({ opened, form, setForm, formError, creating, onClose, onCreate }: Props) {
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
    <Modal opened={opened} onClose={onClose} title="Nova sandbox" centered size="lg">
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
        <Select
          label="Runtime do agente"
          description="Claude CLI exige `claude login` no terminal da sandbox (aba Runtime)."
          data={[
            { value: 'openclaude', label: 'openclaude (catálogo de modelos)' },
            { value: 'claude_cli', label: 'Claude CLI oficial' },
          ]}
          value={form.agentRuntime}
          onChange={(value) => {
            if (value === 'openclaude' || value === 'claude_cli') {
              setForm({ ...form, agentRuntime: value })
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
          <Button variant="default" onClick={onClose} disabled={creating}>
            Cancelar
          </Button>
          <Button onClick={onCreate} loading={creating}>
            Criar
          </Button>
        </Group>
      </Stack>
    </Modal>
  )
}
