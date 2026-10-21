import type { Dispatch, SetStateAction } from 'react'
import {
  Alert,
  Button,
  Checkbox,
  Group,
  Modal,
  Select,
  Stack,
  Switch,
  Text,
  Textarea,
  TextInput,
} from '@/components/ui/legacy'
import type { AdminWorkspace, Repository, Sandbox } from '../../api'
import type { FormState, RepoChoice } from './formState'

type Props = {
  /** Admin de workspace: só CLAUDE.md, chamado obrigatório e modo de planejamento. */
  limited?: boolean
  opened: boolean
  editing: AdminWorkspace | null
  form: FormState
  setForm: Dispatch<SetStateAction<FormState>>
  formError: string | null
  saving: boolean
  sandboxes: Sandbox[]
  repositories: Repository[]
  onClose: () => void
  onSave: () => void
}

export function WorkspaceFormModal({
  opened,
  limited = false,
  editing,
  form,
  setForm,
  formError,
  saving,
  sandboxes,
  repositories,
  onClose,
  onSave,
}: Props) {
  const sandboxRepos = repositories.filter((repo) => repo.sandbox_id === form.sandbox_id)

  function updateRepo(repoId: string, patch: Partial<RepoChoice>, fallbackAlias: string) {
    setForm((prev) => {
      const current = prev.repos[repoId] ?? {
        selected: false,
        alias: fallbackAlias,
        base_branch: '',
        read_only: false,
      }
      return { ...prev, repos: { ...prev.repos, [repoId]: { ...current, ...patch } } }
    })
  }

  return (
    <Modal
      opened={opened}
      onClose={onClose}
      title={editing ? `Editar ${editing.name}` : 'Novo workspace'}
      size="xl"
    >
      <Stack gap="md">
        {formError && (
          <Alert color="red" title="Não foi possível salvar">
            {formError}
          </Alert>
        )}
        {!limited && (
          <>
            <Group grow>
              <TextInput
                label="Nome"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.currentTarget.value })}
                required
              />
              <TextInput
                label="Slug"
                description="Minúsculas, números e hífen. Vira a pasta no sandbox."
                value={form.slug}
                disabled={!!editing}
                onChange={(e) => setForm({ ...form, slug: e.currentTarget.value.toLowerCase() })}
                required
              />
            </Group>
            <Select
              label="Sandbox"
              description={editing ? 'Não muda depois de criado.' : 'Só repositórios desta sandbox podem entrar.'}
              data={sandboxes.map((sandbox) => ({ value: sandbox.id, label: sandbox.name }))}
              value={form.sandbox_id}
              disabled={!!editing}
              onChange={(value) => setForm({ ...form, sandbox_id: value ?? '', repos: {} })}
              allowDeselect={false}
            />

            <Stack gap="xs">
              <Text fw={600} size="sm">
                Repositórios
              </Text>
              {sandboxRepos.length === 0 ? (
                <Text size="sm" c="dimmed">
                  Nenhum repositório cadastrado nesta sandbox.
                </Text>
              ) : (
                sandboxRepos.map((repo) => {
                  const choice = form.repos[repo.id]
                  return (
                    <Group key={repo.id} gap="sm" wrap="nowrap">
                      <Checkbox
                        checked={!!choice?.selected}
                        onChange={(e) => updateRepo(repo.id, { selected: e.currentTarget.checked }, repo.slug)}
                        label={`${repo.name} (${repo.slug})`}
                      />
                      {choice?.selected && (
                        <>
                          <TextInput
                            aria-label={`Alias de ${repo.slug}`}
                            placeholder={`alias (${repo.slug})`}
                            value={choice.alias}
                            onChange={(e) => updateRepo(repo.id, { alias: e.currentTarget.value }, repo.slug)}
                          />
                          <TextInput
                            aria-label={`Branch base de ${repo.slug}`}
                            placeholder={`branch (${repo.default_branch})`}
                            value={choice.base_branch}
                            onChange={(e) => updateRepo(repo.id, { base_branch: e.currentTarget.value }, repo.slug)}
                          />
                          <Checkbox
                            label="Somente leitura (sem edição nem PR)"
                            checked={choice.read_only}
                            onChange={(e) => updateRepo(repo.id, { read_only: e.currentTarget.checked }, repo.slug)}
                          />
                        </>
                      )}
                    </Group>
                  )
                })
              )}
            </Stack>
          </>
        )}

        <Stack gap={4}>
          <Switch
            label="Modo de planejamento"
            checked={form.plan_mode_enabled}
            onChange={(e) => setForm({ ...form, plan_mode_enabled: e.currentTarget.checked })}
          />
          <Text size="xs" c="dimmed">
            Para workspaces onde se programa. Desligado, o chat não oferece o modo e as perguntas são
            respondidas direto.
          </Text>
        </Stack>
        <Stack gap={4}>
          <Switch
            label="Exigir número do chamado"
            checked={form.require_ticket}
            onChange={(e) => setForm({ ...form, require_ticket: e.currentTarget.checked })}
          />
          <Text size="xs" c="dimmed">
            A conversa nova só abre com o número do chamado, que fica gravado nela e sai na exportação
            de chamados.
          </Text>
        </Stack>

        <Textarea
          label="CLAUDE.md do workspace"
          description="Instruções que o agente recebe em todas as conversas deste workspace."
          value={form.claude_md}
          onChange={(e) => setForm({ ...form, claude_md: e.currentTarget.value })}
          minRows={10}
          spellCheck={false}
          style={{ fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace' }}
        />
        <Group justify="flex-end">
          <Button variant="subtle" onClick={onClose}>
            Cancelar
          </Button>
          <Button onClick={onSave} loading={saving} disabled={saving}>
            Salvar
          </Button>
        </Group>
      </Stack>
    </Modal>
  )
}
