import { Badge, Stack, Table, Text } from '@/components/ui/legacy'
import { IconPencil, IconRefresh } from '@tabler/icons-react'
import type { AdminAiProvider } from '../../api'
import { ActionsCell, ActionsHeader, RowActionIcon } from '../../components/TableActions'
import { authStateColor, formatTimestamp } from './form'

type ProvidersTableProps = {
  providers: AdminAiProvider[]
  canSyncProviders: boolean
  syncing: string | null
  onEdit: (provider: AdminAiProvider) => void
  onSync: (providerId: string) => void
}

export function ProvidersTable({
  providers,
  canSyncProviders,
  syncing,
  onEdit,
  onSync,
}: ProvidersTableProps) {
  return (
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
                onClick={() => onEdit(p)}
              >
                <IconPencil size={16} />
              </RowActionIcon>
              <RowActionIcon
                label="Sincronizar provider"
                color="blue"
                loading={syncing === p.id}
                disabled={!canSyncProviders || syncing !== null || !p.active}
                onClick={() => onSync(p.id)}
              >
                <IconRefresh size={16} />
              </RowActionIcon>
            </ActionsCell>
          </Table.Tr>
        ))}
      </Table.Tbody>
    </Table>
  )
}
