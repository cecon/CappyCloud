import { Button, Group, Modal, Stack, Text, TextInput } from '@/components/ui/legacy'
import type { Sandbox } from '../../api'

type Props = {
  cloneFor: Sandbox | null
  cloneName: string
  cloning: boolean
  onNameChange: (value: string) => void
  onClose: () => void
  onClone: () => void
}

export function CloneSandboxModal({ cloneFor, cloneName, cloning, onNameChange, onClose, onClone }: Props) {
  return (
    <Modal
      opened={cloneFor !== null}
      onClose={onClose}
      title={cloneFor ? `Clonar sandbox "${cloneFor.name}"` : 'Clonar sandbox'}
      centered
    >
      <Stack gap="md">
        <Text size="sm" c="dimmed">
          Copia imagem, runtime e variáveis. O container do clone começa em <strong>não criado</strong>.
        </Text>
        <TextInput
          label="Nome do clone"
          value={cloneName}
          onChange={(e) => onNameChange(e.currentTarget.value)}
          required
        />
        <Group justify="flex-end">
          <Button variant="default" onClick={onClose} disabled={cloning}>
            Cancelar
          </Button>
          <Button onClick={onClone} loading={cloning}>
            Clonar
          </Button>
        </Group>
      </Stack>
    </Modal>
  )
}
