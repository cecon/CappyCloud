import type { Dispatch, SetStateAction } from 'react'
import {
  Button,
  Divider,
  Group,
  Modal,
  MultiSelect,
  NumberInput,
  PasswordInput,
  Select,
  Stack,
  Switch,
  TextInput,
} from '@/components/ui/legacy'
import type { AdminAiProvider } from '../../api'
import type { ProviderFormState } from './form'

type ProviderFormModalProps = {
  opened: boolean
  editingProvider: AdminAiProvider | null
  form: ProviderFormState
  setForm: Dispatch<SetStateAction<ProviderFormState>>
  saving: boolean
  canSubmit: boolean
  onClose: () => void
  onSave: () => void
}

export function ProviderFormModal({
  opened,
  editingProvider,
  form,
  setForm,
  saving,
  canSubmit,
  onClose,
  onSave,
}: ProviderFormModalProps) {
  // Lê o valor do evento já no handler: o updater de setForm roda depois, quando
  // event.currentTarget é null (o React zera o evento) e a tela quebrava.
  function setField<K extends keyof ProviderFormState>(key: K, value: ProviderFormState[K]) {
    setForm((prev) => ({ ...prev, [key]: value }))
  }

  function updateBaseUrl(value: string) {
    const lower = value.toLowerCase()
    setForm((prev) => ({
      ...prev,
      base_url: value,
      api_format: lower.includes('/responses')
        ? 'responses'
        : lower.endsWith('/messages')
          ? 'anthropic'
          : prev.api_format,
    }))
  }

  return (
    <Modal
      opened={opened}
      onClose={onClose}
      title={editingProvider ? 'Editar provider LLM' : 'Adicionar provider LLM'}
      size="lg"
    >
      <Stack gap="md">
        <TextInput
          label="Nome"
          placeholder="Azure Eduar"
          value={form.name}
          onChange={(event) => setField('name', event.currentTarget.value)}
          required
        />
        <TextInput
          label="Endpoint / Base URL"
          placeholder="https://.../openai/v1/responses"
          value={form.base_url}
          onChange={(event) => updateBaseUrl(event.currentTarget.value)}
          required
        />
        <Select
          label="Formato da API"
          data={[
            { value: 'chat_completions', label: 'Chat Completions' },
            { value: 'responses', label: 'Responses' },
            { value: 'anthropic', label: 'Anthropic (Messages)' },
          ]}
          description="Para Claude no Azure Foundry use Anthropic: nos outros formatos a Azure descarta as imagens."
          value={form.api_format}
          onChange={(value) =>
            value &&
            setForm((prev) => ({
              ...prev,
              api_format: value as ProviderFormState['api_format'],
            }))
          }
          allowDeselect={false}
        />
        <PasswordInput
          label="Chave"
          placeholder={editingProvider ? 'Deixe em branco para manter a chave atual' : 'API key'}
          value={form.api_key}
          onChange={(event) => setField('api_key', event.currentTarget.value)}
        />

        {!editingProvider && (
          <>
            <Divider />
            <Group grow align="flex-start">
              <TextInput
                label="Modelo / deployment"
                placeholder="gpt-5.4-mini"
                value={form.model_id}
                onChange={(event) => setField('model_id', event.currentTarget.value)}
                required
              />
              <TextInput
                label="Nome exibido"
                placeholder="Azure GPT-5.4 Mini"
                value={form.display_name}
                onChange={(event) => setField('display_name', event.currentTarget.value)}
              />
            </Group>
            <Group grow align="flex-start">
              <NumberInput
                label="Context window"
                min={1}
                value={form.context_window}
                onChange={(value) =>
                  setForm((prev) => ({
                    ...prev,
                    context_window: typeof value === 'number' ? value : prev.context_window,
                  }))
                }
              />
              <Switch
                label="Modelo padrão para texto"
                checked={form.is_default_text}
                disabled={!form.capabilities.includes('text')}
                onChange={(event) => setField('is_default_text', event.currentTarget.checked)}
                mt="xl"
              />
            </Group>
            <MultiSelect
              label="Capabilities do modelo"
              data={[
                { value: 'text', label: 'Texto' },
                { value: 'embedding', label: 'Embedding' },
                { value: 'vision', label: 'Visão' },
                { value: 'audio', label: 'Áudio' },
                { value: 'video', label: 'Vídeo' },
                { value: 'image', label: 'Imagem' },
              ]}
              value={form.capabilities}
              onChange={(value) =>
                setForm((prev) => ({
                  ...prev,
                  capabilities: value.length > 0 ? value : prev.capabilities,
                  is_default_text: value.includes('text') && prev.is_default_text,
                  is_default_embedding:
                    value.includes('embedding') && prev.is_default_embedding,
                }))
              }
              clearable={false}
            />
            <Switch
              label="Modelo padrão para embedding"
              checked={form.is_default_embedding}
              disabled={!form.capabilities.includes('embedding')}
              onChange={(event) => setField('is_default_embedding', event.currentTarget.checked)}
            />
          </>
        )}

        <Switch
          label="Provider ativo"
          checked={form.active}
          onChange={(event) => setField('active', event.currentTarget.checked)}
        />
        <Group justify="flex-end">
          <Button variant="default" onClick={onClose}>
            Cancelar
          </Button>
          <Button loading={saving} disabled={!canSubmit} onClick={onSave}>
            Salvar
          </Button>
        </Group>
      </Stack>
    </Modal>
  )
}
