import { useState } from 'react'
import { Button, Group, Modal, Stack, Switch, TextInput } from '@/components/ui/legacy'
import type { AdminAiProvider, AdminProviderModelCreate } from '../../api'

type AddModelModalProps = {
  provider: AdminAiProvider | null
  saving: boolean
  onClose: () => void
  onSave: (payload: AdminProviderModelCreate) => void
}

export function AddModelModal({ provider, saving, onClose, onSave }: AddModelModalProps) {
  const [modelId, setModelId] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [vision, setVision] = useState(false)

  const trimmedId = modelId.trim()

  return (
    <Modal
      opened={provider !== null}
      onClose={onClose}
      title={provider ? `Adicionar modelo em ${provider.name}` : 'Adicionar modelo'}
    >
      <Stack gap="md">
        <TextInput
          label="Modelo / deployment"
          placeholder="claude-opus-5-5"
          value={modelId}
          onChange={(event) => setModelId(event.currentTarget.value)}
          required
        />
        <TextInput
          label="Nome exibido"
          placeholder="Claude Opus 5.5"
          value={displayName}
          onChange={(event) => setDisplayName(event.currentTarget.value)}
        />
        <Switch
          // Sem visão, o chat troca para outro modelo quando houver imagem anexada.
          label="Lê imagem (visão)"
          checked={vision}
          onChange={(event) => setVision(event.currentTarget.checked)}
        />
        <Group justify="flex-end">
          <Button variant="default" onClick={onClose}>
            Cancelar
          </Button>
          <Button
            loading={saving}
            disabled={trimmedId.length === 0}
            onClick={() =>
              onSave({
                model_id: trimmedId,
                display_name: displayName.trim() || trimmedId,
                capabilities: vision ? ['text', 'vision'] : ['text'],
              })
            }
          >
            Salvar
          </Button>
        </Group>
      </Stack>
    </Modal>
  )
}
