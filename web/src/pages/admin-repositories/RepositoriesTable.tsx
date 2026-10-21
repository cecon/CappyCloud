import { Badge, Group, Stack, Table, Text } from '@/components/ui/legacy'
import { IconFileText, IconPencil, IconRefresh, IconTrash } from '@tabler/icons-react'
import type { Repository } from '../../api'
import { ActionsCell, ActionsHeader, RowActionIcon } from '../../components/TableActions'
import { statusColor } from './form'

type RepositoriesTableProps = {
  repos: Repository[]
  busyId: string | null
  onDocuments: (repo: Repository) => void
  onEdit: (repo: Repository) => void
  onSync: (repoId: string) => void
  onDelete: (repoId: string) => void
}

export function RepositoriesTable({
  repos,
  busyId,
  onDocuments,
  onEdit,
  onSync,
  onDelete,
}: RepositoriesTableProps) {
  return (
    <Table verticalSpacing="sm" highlightOnHover>
      <Table.Thead>
        <Table.Tr>
          <Table.Th>Nome</Table.Th>
          <Table.Th>Slug</Table.Th>
          <Table.Th>Clone URL</Table.Th>
          <Table.Th style={{ width: 120 }}>Branch</Table.Th>
          <Table.Th>Confluence</Table.Th>
          <Table.Th style={{ width: 120 }}>Estado</Table.Th>
          <ActionsHeader width={178} />
        </Table.Tr>
      </Table.Thead>
      <Table.Tbody>
        {repos.map((r) => (
          <Table.Tr key={r.id}>
            <Table.Td>
              <Text fw={500}>{r.name}</Text>
            </Table.Td>
            <Table.Td>
              <Badge variant="light" color="gray">
                {r.slug}
              </Badge>
            </Table.Td>
            <Table.Td>
              <Text size="xs" c="dimmed" style={{ wordBreak: 'break-all' }}>
                {r.clone_url}
              </Text>
            </Table.Td>
            <Table.Td>
              <Text size="sm">{r.default_branch}</Text>
            </Table.Td>
            <Table.Td>
              <Stack gap={4}>
                {r.confluence_url ? (
                  <Text size="xs" c="dimmed">
                    {r.confluence_space || 'Sem space'}
                  </Text>
                ) : (
                  <Text size="xs" c="dimmed">
                    -
                  </Text>
                )}
                {r.confluence_labels?.length > 0 && (
                  <Group gap={4}>
                    {r.confluence_labels.map((label) => (
                      <Badge key={label} size="xs" variant="light" color="blue">
                        {label}
                      </Badge>
                    ))}
                  </Group>
                )}
              </Stack>
            </Table.Td>
            <Table.Td>
              <Badge
                color={statusColor(r.sandbox_status)}
                variant="light"
                title={r.error_message ?? undefined}
              >
                {r.sandbox_status}
              </Badge>
              {r.sandbox_status === 'error' && r.error_message && (
                <Text size="xs" c="red" className="mt-1 max-w-72 break-words" title={r.error_message}>
                  {r.error_message.slice(0, 160)}
                </Text>
              )}
            </Table.Td>
            <ActionsCell>
              <RowActionIcon
                label="Importar documentos"
                color="violet"
                disabled={busyId !== null}
                onClick={() => onDocuments(r)}
              >
                <IconFileText size={16} />
              </RowActionIcon>
              <RowActionIcon
                label="Editar repositório"
                color="gray"
                disabled={busyId !== null}
                onClick={() => onEdit(r)}
              >
                <IconPencil size={16} />
              </RowActionIcon>
              <RowActionIcon
                label="Sincronizar repositório"
                color="blue"
                loading={busyId === r.id}
                disabled={busyId !== null || !r.sandbox_id}
                onClick={() => onSync(r.id)}
              >
                <IconRefresh size={16} />
              </RowActionIcon>
              <RowActionIcon
                label="Remover repositório"
                color="red"
                disabled={busyId !== null}
                onClick={() => onDelete(r.id)}
              >
                <IconTrash size={16} />
              </RowActionIcon>
            </ActionsCell>
          </Table.Tr>
        ))}
      </Table.Tbody>
    </Table>
  )
}
