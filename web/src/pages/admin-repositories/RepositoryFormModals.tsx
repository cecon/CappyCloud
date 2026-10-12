import type { Dispatch, SetStateAction } from 'react'
import { Alert, Button, Group, Modal, Select, Stack, TextInput } from '@/components/ui/legacy'
import type { Repository } from '../../api'
import type { FormState } from './form'

type RepositoryFormModalProps = {
  form: FormState
  setForm: Dispatch<SetStateAction<FormState>>
  formError: string | null
  sandboxOptions: { value: string; label: string }[]
  busy: boolean
  onClose: () => void
  onSubmit: () => void
}

export function CreateRepositoryModal({
  opened,
  form,
  setForm,
  formError,
  sandboxOptions,
  busy,
  onClose,
  onSubmit,
}: RepositoryFormModalProps & { opened: boolean }) {
  return (
    <Modal
      opened={opened}
      onClose={onClose}
      title="Novo repositório"
      centered
      size="lg"
    >
      <Stack gap="md">
        {formError && (
          <Alert color="red" title="Não foi possível criar">
            {formError}
          </Alert>
        )}
        <TextInput
          label="Slug"
          description="Identificador curto; usado em URLs e nomes de pastas."
          value={form.slug}
          onChange={(e) => setForm({ ...form, slug: e.currentTarget.value })}
          required
        />
        <TextInput
          label="Nome"
          value={form.name}
          onChange={(e) => setForm({ ...form, name: e.currentTarget.value })}
          required
        />
        <TextInput
          label="Clone URL"
          placeholder="https://github.com/org/repo.git"
          value={form.clone_url}
          onChange={(e) => setForm({ ...form, clone_url: e.currentTarget.value })}
          required
        />
        <TextInput
          label="Branch default"
          value={form.default_branch}
          onChange={(e) => setForm({ ...form, default_branch: e.currentTarget.value })}
        />
        <TextInput
          label="Confluence URL"
          placeholder="https://confluence.example.com"
          value={form.confluence_url}
          onChange={(e) => setForm({ ...form, confluence_url: e.currentTarget.value })}
        />
        <TextInput
          label="Confluence space"
          placeholder="Frontend"
          value={form.confluence_space}
          onChange={(e) => setForm({ ...form, confluence_space: e.currentTarget.value })}
        />
        <TextInput
          label="Rótulos Confluence"
          placeholder="react, react-dom, react-native"
          value={form.confluence_labels}
          onChange={(e) => setForm({ ...form, confluence_labels: e.currentTarget.value })}
        />
        <TextInput
          label="PAT (opcional)"
          description="Cria um GitProvider implícito com o token cifrado."
          type="password"
          autoComplete="off"
          value={form.pat_token}
          onChange={(e) => setForm({ ...form, pat_token: e.currentTarget.value })}
        />
        <Select
          label="Sandbox"
          description="Onde o repo será clonado. Deixe vazio para usar o primeiro ativo."
          data={sandboxOptions}
          value={form.sandbox_id ?? ''}
          onChange={(v) => setForm({ ...form, sandbox_id: v || null })}
        />
        <Group justify="flex-end" mt="sm">
          <Button variant="default" onClick={onClose} disabled={busy}>
            Cancelar
          </Button>
          <Button onClick={onSubmit} loading={busy}>
            Criar
          </Button>
        </Group>
      </Stack>
    </Modal>
  )
}

export function EditRepositoryModal({
  editingRepo,
  form,
  setForm,
  formError,
  sandboxOptions,
  busy,
  onClose,
  onSubmit,
}: RepositoryFormModalProps & { editingRepo: Repository | null }) {
  return (
    <Modal
      opened={editingRepo !== null}
      onClose={onClose}
      title={editingRepo ? `Editar ${editingRepo.name}` : 'Editar repositório'}
      centered
      size="lg"
    >
      <Stack gap="md">
        {formError && (
          <Alert color="red" title="Não foi possível atualizar">
            {formError}
          </Alert>
        )}
        <TextInput
          label="Slug"
          value={form.slug}
          onChange={(e) => setForm({ ...form, slug: e.currentTarget.value })}
          required
        />
        <TextInput
          label="Nome"
          value={form.name}
          onChange={(e) => setForm({ ...form, name: e.currentTarget.value })}
          required
        />
        <TextInput
          label="Clone URL"
          value={form.clone_url}
          onChange={(e) => setForm({ ...form, clone_url: e.currentTarget.value })}
          required
        />
        <TextInput
          label="Branch default"
          value={form.default_branch}
          onChange={(e) => setForm({ ...form, default_branch: e.currentTarget.value })}
        />
        <TextInput
          label="Confluence URL"
          placeholder="https://confluence.example.com"
          value={form.confluence_url}
          onChange={(e) => setForm({ ...form, confluence_url: e.currentTarget.value })}
        />
        <TextInput
          label="Confluence space"
          placeholder="Frontend"
          value={form.confluence_space}
          onChange={(e) => setForm({ ...form, confluence_space: e.currentTarget.value })}
        />
        <TextInput
          label="Rótulos Confluence"
          placeholder="kubernetes, kubelet"
          value={form.confluence_labels}
          onChange={(e) => setForm({ ...form, confluence_labels: e.currentTarget.value })}
        />
        <TextInput
          label="PAT (opcional)"
          type="password"
          autoComplete="off"
          value={form.pat_token}
          onChange={(e) => setForm({ ...form, pat_token: e.currentTarget.value })}
        />
        <Select
          label="Sandbox"
          data={sandboxOptions}
          value={form.sandbox_id ?? ''}
          onChange={(v) => setForm({ ...form, sandbox_id: v || null })}
        />
        <Group justify="flex-end" mt="sm">
          <Button
            variant="default"
            onClick={onClose}
            disabled={busy}
          >
            Cancelar
          </Button>
          <Button onClick={onSubmit} loading={busy}>
            Salvar
          </Button>
        </Group>
      </Stack>
    </Modal>
  )
}
