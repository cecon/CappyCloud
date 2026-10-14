import {
  Alert,
  Button,
  Checkbox,
  Group,
  Modal,
  PasswordInput,
  Select,
  Stack,
  TextInput,
} from '@/components/ui/legacy'
import type { CreateFormState } from './formState'

type Props = {
  opened: boolean
  form: CreateFormState
  setForm: (form: CreateFormState) => void
  formError: string | null
  creating: boolean
  onClose: () => void
  onCreate: () => void
}

export function CreateUserModal({ opened, form, setForm, formError, creating, onClose, onCreate }: Props) {
  return (
    <Modal opened={opened} onClose={onClose} title="Novo utilizador" centered>
      <Stack gap="md">
        {formError && (
          <Alert color="red" title="Não foi possível criar">
            {formError}
          </Alert>
        )}
        <TextInput
          label="Email"
          placeholder="nome@dominio.com"
          value={form.email}
          onChange={(e) => setForm({ ...form, email: e.currentTarget.value })}
          type="email"
          autoComplete="off"
          required
        />
        <PasswordInput
          label="Senha temporária"
          description="Mínimo 8 caracteres. Use uma senha provisória para o primeiro login."
          value={form.password}
          onChange={(e) => setForm({ ...form, password: e.currentTarget.value })}
          autoComplete="new-password"
          required
        />
        <Checkbox
          label="Exigir troca de senha no primeiro acesso"
          checked={form.mustChangePassword}
          onChange={(e) => setForm({ ...form, mustChangePassword: e.currentTarget.checked })}
        />
        <Select
          label="Papel"
          data={[
            { value: 'user', label: 'USER — uso normal' },
            { value: 'admin', label: 'ADMIN — administração total' },
          ]}
          value={form.role}
          onChange={(value) => {
            if (value === 'admin' || value === 'user') {
              setForm({ ...form, role: value })
            }
          }}
          allowDeselect={false}
        />
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
