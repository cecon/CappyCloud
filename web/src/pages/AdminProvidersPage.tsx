import { useCallback, useEffect, useState } from 'react'
import {
  Alert,
  Button,
  Container,
  Group,
  Loader,
  Paper,
  Stack,
  Text,
  Title,
} from '@/components/ui/legacy'
import { IconPlus } from '@tabler/icons-react'
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
import { useCurrentUser } from '../hooks/useCurrentUser'
import { EMPTY_FORM, formFromProvider, type ProviderFormState } from './admin-providers/form'
import { ProviderFormModal } from './admin-providers/ProviderFormModal'
import { ProvidersTable } from './admin-providers/ProvidersTable'

export function AdminProvidersPage() {
  const currentUser = useCurrentUser()
  const canSyncProviders =
    currentUser.status === 'ready' && currentUser.user.role === 'admin'
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
          <Alert color="yellow" title="Somente ADMIN sincroniza providers">
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
            <ProvidersTable
              providers={providers}
              canSyncProviders={canSyncProviders}
              syncing={syncing}
              onEdit={openEditForm}
              onSync={(providerId) => void handleSync(providerId)}
            />
          )}
        </Paper>

        <ProviderFormModal
          opened={formOpened}
          editingProvider={editingProvider}
          form={form}
          setForm={setForm}
          saving={saving}
          canSubmit={canSubmit}
          onClose={() => setFormOpened(false)}
          onSave={() => void handleSaveProvider()}
        />
      </Stack>
    </Container>
  )
}
