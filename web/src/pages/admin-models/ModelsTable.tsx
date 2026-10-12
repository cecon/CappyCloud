import { Badge, Group, Select, Stack, Switch, Table, Text } from '@/components/ui/legacy'
import type { AdminAiProvider, AiModel, ModelTier } from '../../api'
import { capabilityColor, formatPrice, tierColor } from './helpers'

type ModelsTableProps = {
  models: AiModel[]
  providersById: Map<string, AdminAiProvider>
  canManageCatalog: boolean
  busyId: string | null
  onToggleActive: (model: AiModel) => void
  onChangeTier: (model: AiModel, tier: ModelTier) => void
  onToggleCapability: (model: AiModel, capability: string) => void
  onToggleDefault: (model: AiModel, capability: 'text' | 'embedding') => void
}

export function ModelsTable({
  models,
  providersById,
  canManageCatalog,
  busyId,
  onToggleActive,
  onChangeTier,
  onToggleCapability,
  onToggleDefault,
}: ModelsTableProps) {
  return (
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
                    onChange={() => onToggleCapability(m, 'text')}
                  />
                  <Switch
                    size="xs"
                    label="embedding"
                    checked={m.capabilities?.includes('embedding') ?? false}
                    disabled={!canManageCatalog || busyId === m.id}
                    onChange={() => onToggleCapability(m, 'embedding')}
                  />
                </Group>
              </Table.Td>
              <Table.Td>
                <Switch
                  checked={!!m.is_default?.text}
                  disabled={!canManageCatalog || busyId === m.id}
                  onChange={() => onToggleDefault(m, 'text')}
                />
              </Table.Td>
              <Table.Td>
                <Switch
                  checked={!!m.is_default?.embedding}
                  disabled={!canManageCatalog || busyId === m.id}
                  onChange={() => onToggleDefault(m, 'embedding')}
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
                  onChange={(v) => v && onChangeTier(m, v as ModelTier)}
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
                  onChange={() => onToggleActive(m)}
                />
              </Table.Td>
            </Table.Tr>
          )
        })}
      </Table.Tbody>
    </Table>
  )
}
