import { useCallback, useEffect, useState } from 'react'
import {
  Alert,
  Badge,
  Button,
  Container,
  Divider,
  Group,
  Loader,
  Modal,
  MultiSelect,
  NumberInput,
  Paper,
  PasswordInput,
  Select,
  Stack,
  Switch,
  Table,
  Text,
  TextInput,
  Title,
} from '@/components/ui/legacy'
import { IconPencil, IconPlus, IconRefresh } from '@tabler/icons-react'
import {
  createAdminProvider,
  type AdminAiProvider,
  type AdminProviderCreate,
  type AiModelSyncResult,
  errorToUserMessage,
  fetchAdminProviders,
  getToken,
  patchAdminProvider,
  syncAdminProvider,
} from '../api'
import { ActionsCell, ActionsHeader, RowActionIcon } from '../components/TableActions'
import { useCurrentUser } from '../hooks/useCurrentUser'

function formatTimestamp(iso: string | null): string {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleString('pt-PT')
  } catch {
    return iso
  }
}

function authStateColor(state: AdminAiProvider['auth_state']): string {
  if (state === 'configured') return 'green'
  if (state === 'catalog-only') return 'blue'
  if (state === 'inactive') return 'gray'
  return 'yellow'
}

type ProviderFormState = {
  name: string
  base_url: string
  api_format: 'chat_completions' | 'responses'
  api_key: string
  model_id: string
  display_name: string
  context_window: number
  capabilities: string[]
  active: boolean
  is_default_text: boolean
  is_default_embedding: boolean
}

const EMPTY_FORM: ProviderFormState = {
  name: '',
  base_url: '',
  api_format: 'chat_completions',
  api_key: '',
  model_id: '',
  display_name: '',
  context_window: 200000,
  capabilities: ['text'],
  active: true,
  is_default_text: false,
  is_default_embedding: false,
}

function formFromProvider(provider: AdminAiProvider): ProviderFormState {
  return {
    ...EMPTY_FORM,
    name: provider.name,
    base_url: provider.base_url,
    api_format: provider.api_format,
    active: provider.active,
  }
}

export function AdminProvidersPage() {
  const currentUser = useCurrentUser()
  const canSyncProviders =
    currentUser.status === 'ready' && currentUser.user.is_super_admin
  const [providers, setProviders] = useState<AdminAiProvider[] | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [syncing, setSyncing] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [lastResult, setLastResult] = useState<AiModelSyncResult | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [formOpened, setFormOpened] = useState(false)
  const [editingProvider, setEditingProvider] = useState<AdminAiProvider | null>(null)
  const [form, setForm] = useState<ProviderFormState>(EMPTY_FORM)

  const reload = useCallback(async () => {
    const token = getToken()
    if (!token) return
    try {
      const list = await fetchAdminProviders(token)
      setProviders(list)
      setLoadError(null)
    } catch (err) {
      setLoadError(errorToUserMessage(err))
    }
  }, [])

  useEffect(() => {
    void reload()
  }, [reload])

  async function handleSync(providerId: string) {
    const token = getToken()
    if (!token) return
    setSyncing(providerId)
    setActionError(null)
    setLastResult(null)
    try {
      const result = await syncAdminProvider(token, providerId)
      setLastResult(result)
      await reload()
    } catch (err) {
      setActionError(errorToUserMessage(err))
    } finally {
      setSyncing(null)
    }
  }

  function openCreateForm() {
    setEditingProvider(null)
    setForm(EMPTY_FORM)
    setActionError(null)
    setFormOpened(true)
  }

  function openEditForm(provider: AdminAiProvider) {
    setEditingProvider(provider)
    setForm(formFromProvider(provider))
    setActionError(null)
    setFormOpened(true)
  }

  function updateBaseUrl(value: string) {
    setForm((prev) => ({
      ...prev,
      base_url: value,
      api_format: value.toLowerCase().includes('/responses') ? 'responses' : prev.api_format,
    }))
  }

  async function handleSaveProvider() {
    const token = getToken()
    if (!token) return
    setSaving(true)
    setActionError(null)
    try {
      if (editingProvider) {
        await patchAdminProvider(token, editingProvider.id, {
          name: form.name.trim(),
          base_url: form.base_url.trim(),
          api_format: form.api_format,
          api_key: form.api_key.trim() || undefined,
          active: form.active,
        })
      } else {
        const payload: AdminProviderCreate = {
          name: form.name.trim(),
          base_url: form.base_url.trim(),
          api_format: form.api_format,
          api_key: form.api_key.trim(),
          model_id: form.model_id.trim(),
          display_name: form.display_name.trim(),
          capabilities: form.capabilities,
          context_window: form.context_window,
          active: form.active,
          is_default_text: form.is_default_text,
          is_default_embedding: form.is_default_embedding,
        }
        await createAdminProvider(token, payload)
      }
      setFormOpened(false)
      await reload()
    } catch (err) {
      setActionError(errorToUserMessage(err))
    } finally {
      setSaving(false)
    }
  }

  const canSubmit =
    form.name.trim().length > 0 &&
    form.base_url.trim().length > 0 &&
    (editingProvider !== null || form.model_id.trim().length > 0)

  return (
    <Container size="lg" py="xl">
      <Stack gap="lg">
        <Group justify="space-between" align="flex-start">
          <Stack gap={4}>
            <Title order={2}>Providers LLM</Title>
            <Text c="dimmed" size="xs">
              Sync atualiza o catalogo dinamico usado pelo chat: modelos novos, modelos retirados,
              capabilities e precos globais.
            </Text>
            <Text c="dimmed" size="sm">
              Provedores de modelos IA (OpenRouter, Azure AI Foundry, OpenAI...). Providers manuais
              usam a chave cadastrada no runtime do chat.
            </Text>
          </Stack>
          <Button
            leftSection={<IconPlus size={16} />}
            disabled={!canSyncProviders}
            onClick={openCreateForm}
          >
            Adicionar provider
          </Button>
        </Group>

        {actionError && (
          <Alert color="red" title="Falha no sync" withCloseButton onClose={() => setActionError(null)}>
            {actionError}
          </Alert>
        )}

        {!canSyncProviders && (
          <Alert color="yellow" title="Somente super admin sincroniza providers">
            A sincronização pode ativar novos modelos free e atualizar preços globais.
          </Alert>
        )}

        {lastResult && (
          <Alert color="green" title="Sync concluído" withCloseButton onClose={() => setLastResult(null)}>
            {lastResult.fetched} modelos do provider — {lastResult.created} criados,{' '}
            {lastResult.updated} atualizados, {lastResult.deactivated} desativados. O seletor do
            chat passa a refletir apenas modelos ativos e autorizados.
          </Alert>
        )}

        <Paper withBorder p="md" radius="md">
          {loadError ? (
            <Alert color="red" title="Não foi possível carregar providers">
              {loadError}
            </Alert>
          ) : providers === null ? (
            <Group justify="center" py="xl">
              <Loader />
            </Group>
          ) : providers.length === 0 ? (
            <Text c="dimmed" ta="center" py="xl">
              Nenhum provider cadastrado.
            </Text>
          ) : (
            <Table verticalSpacing="sm" highlightOnHover>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Nome</Table.Th>
                  <Table.Th>Base URL</Table.Th>
                  <Table.Th style={{ width: 140 }}>Formato</Table.Th>
                  <Table.Th style={{ width: 90 }}>Modelos</Table.Th>
                  <Table.Th style={{ width: 90 }}>Estado</Table.Th>
                  <Table.Th style={{ width: 190 }}>Autenticação</Table.Th>
                  <Table.Th style={{ width: 180 }}>Último sync</Table.Th>
                  <ActionsHeader width={112} />
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {providers.map((p) => (
                  <Table.Tr key={p.id}>
                    <Table.Td>
                      <Text fw={500}>{p.name}</Text>
                    </Table.Td>
                    <Table.Td>
                      <Text size="xs" c="dimmed">
                        {p.base_url}
                      </Text>
                    </Table.Td>
                    <Table.Td>
                      <Badge variant="light" color={p.api_format === 'responses' ? 'cyan' : 'gray'}>
                        {p.api_format === 'responses' ? 'Responses' : 'Chat'}
                      </Badge>
                    </Table.Td>
                    <Table.Td>
                      <Badge variant="light" color="blue">
                        {p.models_count}
                      </Badge>
                    </Table.Td>
                    <Table.Td>
                      <Badge color={p.active ? 'green' : 'gray'} variant={p.active ? 'filled' : 'light'}>
                        {p.active ? 'ativo' : 'inativo'}
                      </Badge>
                    </Table.Td>
                    <Table.Td>
                      <Stack gap={2}>
                        <Badge color={authStateColor(p.auth_state)} variant="light">
                          {p.auth_label}
                        </Badge>
                        <Text size="xs" c="dimmed">
                          {p.auth_next_action}
                        </Text>
                      </Stack>
                    </Table.Td>
                    <Table.Td>
                      <Text size="xs">{formatTimestamp(p.last_synced_at)}</Text>
                    </Table.Td>
                    <ActionsCell>
                      <RowActionIcon
                        label="Editar provider"
                        color="gray"
                        disabled={!canSyncProviders || syncing !== null}
                        onClick={() => openEditForm(p)}
                      >
                        <IconPencil size={16} />
                      </RowActionIcon>
                      <RowActionIcon
                        label="Sincronizar provider"
                        color="blue"
                        loading={syncing === p.id}
                        disabled={!canSyncProviders || syncing !== null || !p.active}
                        onClick={() => void handleSync(p.id)}
                      >
                        <IconRefresh size={16} />
                      </RowActionIcon>
                    </ActionsCell>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          )}
        </Paper>

        <Modal
          opened={formOpened}
          onClose={() => setFormOpened(false)}
          title={editingProvider ? 'Editar provider LLM' : 'Adicionar provider LLM'}
          size="lg"
        >
          <Stack gap="md">
            <TextInput
              label="Nome"
              placeholder="Azure Eduar"
              value={form.name}
              onChange={(event) => setForm((prev) => ({ ...prev, name: event.currentTarget.value }))}
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
              ]}
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
              onChange={(event) =>
                setForm((prev) => ({ ...prev, api_key: event.currentTarget.value }))
              }
            />

            {!editingProvider && (
              <>
                <Divider />
                <Group grow align="flex-start">
                  <TextInput
                    label="Modelo / deployment"
                    placeholder="gpt-5.4-mini"
                    value={form.model_id}
                    onChange={(event) =>
                      setForm((prev) => ({ ...prev, model_id: event.currentTarget.value }))
                    }
                    required
                  />
                  <TextInput
                    label="Nome exibido"
                    placeholder="Azure GPT-5.4 Mini"
                    value={form.display_name}
                    onChange={(event) =>
                      setForm((prev) => ({ ...prev, display_name: event.currentTarget.value }))
                    }
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
                    onChange={(event) =>
                      setForm((prev) => ({
                        ...prev,
                        is_default_text: event.currentTarget.checked,
                      }))
                    }
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
                  onChange={(event) =>
                    setForm((prev) => ({
                      ...prev,
                      is_default_embedding: event.currentTarget.checked,
                    }))
                  }
                />
              </>
            )}

            <Switch
              label="Provider ativo"
              checked={form.active}
              onChange={(event) =>
                setForm((prev) => ({ ...prev, active: event.currentTarget.checked }))
              }
            />
            <Group justify="flex-end">
              <Button variant="default" onClick={() => setFormOpened(false)}>
                Cancelar
              </Button>
              <Button loading={saving} disabled={!canSubmit} onClick={() => void handleSaveProvider()}>
                Salvar
              </Button>
            </Group>
          </Stack>
        </Modal>
      </Stack>
    </Container>
  )
}
