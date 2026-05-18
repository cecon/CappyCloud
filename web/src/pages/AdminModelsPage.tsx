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

export function AdminModelsPage() {
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

  return (
    <Container size="lg" py="xl">
      <Stack gap="lg">
        <Stack gap={4}>
          <Title order={2}>Modelos LLM</Title>
          <Text c="dimmed" size="sm">
            Catálogo sincronizado a partir dos providers. Tier é derivado do preço, mas pode ser
            ajustado manualmente. Modelos desativados não aparecem para utilizadores.
          </Text>
        </Stack>

        {actionError && (
          <Alert color="red" title="Falha" withCloseButton onClose={() => setActionError(null)}>
            {actionError}
          </Alert>
        )}

        <Paper withBorder p="md" radius="md">
          <Group gap="md" mb="md">
            <Select
              label="Provider"
              w={240}
              data={[
                { value: 'all', label: 'Todos' },
                ...providers.map((p) => ({ value: p.id, label: p.name })),
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
                  <Table.Th style={{ width: 140 }}>Tier</Table.Th>
                  <Table.Th style={{ width: 110 }}>In $/1M</Table.Th>
                  <Table.Th style={{ width: 110 }}>Out $/1M</Table.Th>
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
                        <Select
                          size="xs"
                          data={[
                            { value: 'free', label: 'free' },
                            { value: 'paid', label: 'paid' },
                            { value: 'unknown', label: 'unknown' },
                          ]}
                          value={m.tier}
                          onChange={(v) => v && void changeTier(m, v as ModelTier)}
                          disabled={busyId === m.id}
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
                        <Switch
                          checked={m.active}
                          disabled={busyId === m.id}
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
