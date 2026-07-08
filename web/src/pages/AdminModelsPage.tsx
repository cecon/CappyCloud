import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Alert,
  Badge,
  Container,
  Group,
  Loader,
  Paper,
  Select,
  Stack,
  Switch,
  Table,
  Text,
  Title,
} from '@mantine/core'
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

type TierFilter = 'all' | ModelTier

const TIER_OPTIONS: { value: TierFilter; label: string }[] = [
  { value: 'all', label: 'Todos' },
  { value: 'free', label: 'Free' },
  { value: 'paid', label: 'Paid' },
  { value: 'unknown', label: 'Sem preço' },
]

function tierColor(t: ModelTier): string {
  if (t === 'free') return 'green'
  if (t === 'paid') return 'grape'
  return 'gray'
}

function formatPrice(value: number | null): string {
  if (value === null) return '—'
  return `$${value.toFixed(2)}`
}

function capabilityColor(capability: string): string {
  if (capability === 'embedding') return 'cyan'
  if (capability === 'vision') return 'grape'
  if (capability === 'text') return 'blue'
  return 'gray'
}

export function AdminModelsPage() {
  const currentUser = useCurrentUser()
  const canManageCatalog =
    currentUser.status === 'ready' && currentUser.user.is_super_admin
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
          <Alert color="yellow" title="Somente super admin altera o catálogo">
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
            <Table verticalSpacing="sm" highlightOnHover>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Nome</Table.Th>
                  <Table.Th style={{ width: 140 }}>Provider</Table.Th>
                  <Table.Th style={{ width: 190 }}>Capabilities</Table.Th>
                  <Table.Th style={{ width: 130 }}>Default texto</Table.Th>
                  <Table.Th style={{ width: 150 }}>Default embedding</Table.Th>
                  <Table.Th style={{ width: 140 }}>Tier</Table.Th>
                  <Table.Th style={{ width: 110 }}>In $/1M</Table.Th>
                  <Table.Th style={{ width: 110 }}>Out $/1M</Table.Th>
                  <Table.Th style={{ width: 120 }}>Catalogo</Table.Th>
                  <Table.Th style={{ width: 90 }}>Ativo</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {models.map((m) => {
                  const prov = providersById.get(m.provider_id)
                  return (
                    <Table.Tr key={m.id}>
                      <Table.Td>
                        <Stack gap={0}>
                          <Text fw={500}>{m.display_name}</Text>
                          <Text size="xs" c="dimmed">
                            {m.model_id}
                          </Text>
                        </Stack>
                      </Table.Td>
                      <Table.Td>
                        <Text size="sm">{prov?.name ?? '—'}</Text>
                      </Table.Td>
                      <Table.Td>
                        <Group gap={6}>
                          {(m.capabilities ?? []).map((capability) => (
                            <Badge
                              key={capability}
                              size="xs"
                              variant="light"
                              color={capabilityColor(capability)}
                            >
                              {capability}
                            </Badge>
                          ))}
                        </Group>
                        <Group gap="xs" mt={6}>
                          <Switch
                            size="xs"
                            label="text"
                            checked={m.capabilities?.includes('text') ?? false}
                            disabled={!canManageCatalog || busyId === m.id}
                            onChange={() => void toggleCapability(m, 'text')}
                          />
                          <Switch
                            size="xs"
                            label="embedding"
                            checked={m.capabilities?.includes('embedding') ?? false}
                            disabled={!canManageCatalog || busyId === m.id}
                            onChange={() => void toggleCapability(m, 'embedding')}
                          />
                        </Group>
                      </Table.Td>
                      <Table.Td>
                        <Switch
                          checked={!!m.is_default?.text}
                          disabled={!canManageCatalog || busyId === m.id}
                          onChange={() => void toggleDefault(m, 'text')}
                        />
                      </Table.Td>
                      <Table.Td>
                        <Switch
                          checked={!!m.is_default?.embedding}
                          disabled={!canManageCatalog || busyId === m.id}
                          onChange={() => void toggleDefault(m, 'embedding')}
                        />
                      </Table.Td>
                      <Table.Td>
                        <Select
                          size="xs"
                          data={[
                            { value: 'free', label: 'free' },
                            { value: 'paid', label: 'paid' },
                            { value: 'unknown', label: 'unknown' },
                          ]}
                          value={m.tier}
                          onChange={(v) => v && void changeTier(m, v as ModelTier)}
                          disabled={!canManageCatalog || busyId === m.id}
                          allowDeselect={false}
                          leftSection={
                            <Badge size="xs" variant="dot" color={tierColor(m.tier)}>
                              {' '}
                            </Badge>
                          }
                        />
                      </Table.Td>
                      <Table.Td>
                        <Text size="sm">{formatPrice(m.input_cost_per_1m_usd)}</Text>
                      </Table.Td>
                      <Table.Td>
                        <Text size="sm">{formatPrice(m.output_cost_per_1m_usd)}</Text>
                      </Table.Td>
                      <Table.Td>
                        <Badge
                          size="xs"
                          variant="light"
                          color={prov?.active && m.active ? 'green' : 'gray'}
                        >
                          {prov?.active && m.active ? 'autorizado' : 'indisponivel'}
                        </Badge>
                      </Table.Td>
                      <Table.Td>
                        <Switch
                          checked={m.active}
                          disabled={!canManageCatalog || busyId === m.id}
                          onChange={() => void toggleActive(m)}
                        />
                      </Table.Td>
                    </Table.Tr>
                  )
                })}
              </Table.Tbody>
            </Table>
          )}
        </Paper>
      </Stack>
    </Container>
  )
}
