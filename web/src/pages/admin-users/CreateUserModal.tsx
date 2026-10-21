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
  /** Admin de workspace: escolhe o workspace; papel e troca de senha ficam fixos. */
  workspaces?: Array<{ id: string; name: string }> | null
  opened: boolean
  form: CreateFormState
  setForm: (form: CreateFormState) => void
  formError: string | null
  creating: boolean
  onClose: () => void
  onCreate: () => void
}

export function CreateUserModal({
  workspaces = null,
  opened,
  form,
  setForm,
  formError,
  creating,
  onClose,
  onCreate,
}: Props) {
  const memberMode = workspaces !== null
  return (
    <Modal opened={opened} onClose={onClose} title={memberMode ? 'Incluir pessoa' : 'Novo utilizador'} centered>
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
        {memberMode ? (
          <Select
            label="Workspace"
            description="A pessoa entra como USER com acesso a este workspace e os mesmos modelos LLM que você. Se o e-mail já existir, ela só ganha o acesso."
            data={(workspaces ?? []).map((ws) => ({ value: ws.id, label: ws.name }))}
            value={form.workspaceId || null}
            onChange={(value) => setForm({ ...form, workspaceId: value ?? '' })}
            allowDeselect={false}
          />
        ) : (
          <>
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
          </>
        )}
        <Group justify="flex-end" mt="sm">
          <Button variant="default" onClick={onClose} disabled={creating}>
            Cancelar
          </Button>
          <Button onClick={onCreate} loading={creating}>
            {memberMode ? 'Incluir' : 'Criar'}
          </Button>
        </Group>
      </Stack>
    </Modal>
  )
}
