import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Alert,
  Container,
  Group,
  Loader,
  Paper,
  Select,
  Stack,
  Switch,
  Text,
  Title,
} from '@/components/ui/legacy'
import {
  type AdminAiProvider,
  type AiModel,
  errorToUserMessage,
  fetchAdminModels,
  fetchAdminProviders,
  getToken,
  type ModelTier,
  patchAdminModel,
} from '../api'
import { useCurrentUser } from '../hooks/useCurrentUser'
import { TIER_OPTIONS, type TierFilter } from './admin-models/helpers'
import { ModelsTable } from './admin-models/ModelsTable'

export function AdminModelsPage() {
  const currentUser = useCurrentUser()
  const canManageCatalog =
    currentUser.status === 'ready' && currentUser.user.role === 'admin'
  const [providers, setProviders] = useState<AdminAiProvider[]>([])
  const [models, setModels] = useState<AiModel[] | null>(null)
  const [tier, setTier] = useState<TierFilter>('all')
  const [providerId, setProviderId] = useState<string | 'all'>('all')
  const [onlyActive, setOnlyActive] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [busyId, setBusyId] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)

  useEffect(() => {
    const token = getToken()
    if (!token) return
    void (async () => {
      try {
        const ps = await fetchAdminProviders(token)
        setProviders(ps)
      } catch (err) {
        setLoadError(errorToUserMessage(err))
      }
    })()
  }, [])

  const reload = useCallback(async () => {
    const token = getToken()
    if (!token) return
    setModels(null)
    try {
      const list = await fetchAdminModels(token, {
        tier: tier === 'all' ? undefined : tier,
        provider_id: providerId === 'all' ? undefined : providerId,
        only_active: onlyActive,
      })
      setModels(list)
      setLoadError(null)
    } catch (err) {
      setLoadError(errorToUserMessage(err))
    }
  }, [tier, providerId, onlyActive])

  useEffect(() => {
    void reload()
  }, [reload])

  const providersById = useMemo(
    () => new Map(providers.map((p) => [p.id, p])),
    [providers],
  )
  const activeProviders = useMemo(
    () => providers.filter((p) => p.active),
    [providers],
  )

  useEffect(() => {
    if (providerId !== 'all' && !activeProviders.some((p) => p.id === providerId)) {
      setProviderId('all')
    }
  }, [activeProviders, providerId])

  async function toggleActive(model: AiModel) {
    const token = getToken()
    if (!token) return
    setBusyId(model.id)
    setActionError(null)
    try {
      const updated = await patchAdminModel(token, model.id, { active: !model.active })
      setModels((prev) => (prev ? prev.map((m) => (m.id === updated.id ? updated : m)) : prev))
    } catch (err) {
      setActionError(errorToUserMessage(err))
    } finally {
      setBusyId(null)
    }
  }

  async function changeTier(model: AiModel, newTier: ModelTier) {
    if (newTier === model.tier) return
    const token = getToken()
    if (!token) return
    setBusyId(model.id)
    setActionError(null)
    try {
      const updated = await patchAdminModel(token, model.id, { tier: newTier })
      setModels((prev) => (prev ? prev.map((m) => (m.id === updated.id ? updated : m)) : prev))
    } catch (err) {
      setActionError(errorToUserMessage(err))
    } finally {
      setBusyId(null)
    }
  }

  async function toggleCapability(model: AiModel, capability: string) {
    const token = getToken()
    if (!token) return
    const current = new Set(model.capabilities ?? [])
    if (current.has(capability)) {
      current.delete(capability)
    } else {
      current.add(capability)
    }
    const nextCapabilities = Array.from(current)
    if (nextCapabilities.length === 0) return
    setBusyId(model.id)
    setActionError(null)
    try {
      const updated = await patchAdminModel(token, model.id, {
        capabilities: nextCapabilities,
      })
      setModels((prev) => (prev ? prev.map((m) => (m.id === updated.id ? updated : m)) : prev))
    } catch (err) {
      setActionError(errorToUserMessage(err))
    } finally {
      setBusyId(null)
    }
  }

  async function toggleDefault(model: AiModel, capability: 'text' | 'embedding') {
    const token = getToken()
    if (!token) return
    const enabled = !model.is_default?.[capability]
    setBusyId(model.id)
    setActionError(null)
    try {
      const updated = await patchAdminModel(token, model.id, {
        ...(capability === 'text'
          ? { is_default_text: enabled }
          : { is_default_embedding: enabled }),
      })
      setModels((prev) => {
        if (!prev) return prev
        if (!enabled) return prev.map((m) => (m.id === updated.id ? updated : m))
        return prev.map((m) => {
          if (m.id === updated.id) return updated
          return { ...m, is_default: { ...(m.is_default ?? {}), [capability]: false } }
        })
      })
    } catch (err) {
      setActionError(errorToUserMessage(err))
    } finally {
      setBusyId(null)
    }
  }

  return (
    <Container size="lg" py="xl">
      <Stack gap="lg">
        <Stack gap={4}>
          <Title order={2}>Modelos LLM</Title>
          <Text c="dimmed" size="xs">
            O chat usa apenas modelos ativos no catalogo autorizado; preco e capabilities vem do
            provider sincronizado ou do ajuste administrativo explicito.
          </Text>
          <Text c="dimmed" size="sm">
            Catálogo sincronizado a partir dos providers ativos. Tier é derivado do preço, mas
            pode ser ajustado manualmente. Modelos desativados não aparecem para utilizadores.
          </Text>
        </Stack>

        {actionError && (
          <Alert color="red" title="Falha" withCloseButton onClose={() => setActionError(null)}>
            {actionError}
          </Alert>
        )}

        {!canManageCatalog && (
          <Alert color="yellow" title="Somente ADMIN altera o catálogo">
            Você pode consultar os modelos, mas ativação global e tier são bloqueados.
          </Alert>
        )}

        <Paper withBorder p="md" radius="md">
          <Group gap="md" mb="md">
            <Select
              label="Provider"
              w={240}
              data={[
                { value: 'all', label: 'Todos ativos' },
                ...activeProviders.map((p) => ({ value: p.id, label: p.name })),
              ]}
              value={providerId}
              onChange={(v) => v && setProviderId(v as string)}
              allowDeselect={false}
            />
            <Select
              label="Tier"
              w={160}
              data={TIER_OPTIONS}
              value={tier}
              onChange={(v) => v && setTier(v as TierFilter)}
              allowDeselect={false}
            />
            <Switch
              label="Só ativos"
              checked={onlyActive}
              onChange={(e) => setOnlyActive(e.currentTarget.checked)}
              mt="lg"
            />
          </Group>

          {loadError ? (
            <Alert color="red" title="Não foi possível carregar modelos">
              {loadError}
            </Alert>
          ) : models === null ? (
            <Group justify="center" py="xl">
              <Loader />
            </Group>
          ) : models.length === 0 ? (
            <Text c="dimmed" ta="center" py="xl">
              Nenhum modelo bate com os filtros.
            </Text>
          ) : (
            <ModelsTable
              models={models}
              providersById={providersById}
              canManageCatalog={canManageCatalog}
              busyId={busyId}
              onToggleActive={(m) => void toggleActive(m)}
              onChangeTier={(m, t) => void changeTier(m, t)}
              onToggleCapability={(m, c) => void toggleCapability(m, c)}
              onToggleDefault={(m, c) => void toggleDefault(m, c)}
            />
          )}
        </Paper>
      </Stack>
    </Container>
  )
}
