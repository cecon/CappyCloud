import { Badge, Group, Table, Text } from '@/components/ui/legacy'
import { IconBrain, IconFileSpreadsheet, IconPencil, IconRefresh, IconTrash } from '@tabler/icons-react'
import {
  type AdminWorkspace,
  deleteAdminWorkspace,
  downloadWorkspaceTickets,
  syncAdminWorkspace,
} from '../../api'
import { ActionsCell, ActionsHeader, RowActionIcon } from '../../components/TableActions'
import { WorkspaceKnowledgeBadges } from '../../components/WorkspaceKnowledgeBadges'
import { SYNC_COLORS } from './formState'

type Props = {
  workspaces: AdminWorkspace[]
  sandboxName: Map<string, string>
  busyId: string | null
  onEdit: (ws: AdminWorkspace) => void
  onKnowledge: (ws: AdminWorkspace) => void
  runAction: (id: string, action: (token: string) => Promise<unknown>) => void
}

export function WorkspacesTable({ workspaces, sandboxName, busyId, onEdit, onKnowledge, runAction }: Props) {
  return (
    <Table verticalSpacing="sm" highlightOnHover>
      <Table.Thead>
        <Table.Tr>
          <Table.Th>Nome</Table.Th>
          <Table.Th>Slug</Table.Th>
          <Table.Th>Sandbox</Table.Th>
          <Table.Th>Repositórios</Table.Th>
          <Table.Th style={{ width: 120 }}>Sincronização</Table.Th>
          <Table.Th>Conhecimento</Table.Th>
          <ActionsHeader width={172} />
        </Table.Tr>
      </Table.Thead>
      <Table.Tbody>
        {workspaces.map((ws) => (
          <Table.Tr key={ws.id}>
            <Table.Td>
              <Text fw={500}>{ws.name}</Text>
            </Table.Td>
            <Table.Td>
              <Badge variant="light" color="gray">
                {ws.slug}
              </Badge>
            </Table.Td>
            <Table.Td>
              <Text size="sm">{sandboxName.get(ws.sandbox_id) ?? '—'}</Text>
            </Table.Td>
            <Table.Td>
              <Group gap={4}>
                {ws.repositories.length === 0 && (
                  <Text size="xs" c="dimmed">
                    nenhum
                  </Text>
                )}
                {ws.repositories.map((link) => (
                  <Badge
                    key={link.repository_id}
                    size="xs"
                    variant="light"
                    color={link.sandbox_status === 'cloned' ? 'blue' : 'yellow'}
                  >
                    {link.alias}
                    {link.read_only ? ' · leitura' : ''}
                  </Badge>
                ))}
              </Group>
            </Table.Td>
            <Table.Td>
              <Badge color={SYNC_COLORS[ws.sync_status] ?? 'gray'} variant="light">
                {ws.sync_status}
              </Badge>
              {ws.sync_error && (
                <Text size="xs" c="red" title={ws.sync_error}>
                  {ws.sync_error.slice(0, 60)}
                </Text>
              )}
            </Table.Td>
            <Table.Td>
              <WorkspaceKnowledgeBadges workspaceId={ws.id} onOpen={() => onKnowledge(ws)} />
            </Table.Td>
            <ActionsCell>
              <RowActionIcon
                label="Editar workspace"
                color="gray"
                disabled={busyId !== null}
                onClick={() => onEdit(ws)}
              >
                <IconPencil size={16} />
              </RowActionIcon>
              <RowActionIcon label="Conhecimento (grafo e memória)" color="violet" onClick={() => onKnowledge(ws)}>
                <IconBrain size={16} />
              </RowActionIcon>
              <RowActionIcon
                label="Exportar chamados (CSV)"
                color="green"
                disabled={busyId !== null}
                onClick={() => runAction(ws.id, (t) => downloadWorkspaceTickets(t, ws.id, ws.slug))}
              >
                <IconFileSpreadsheet size={16} />
              </RowActionIcon>
              <RowActionIcon
                label="Sincronizar no sandbox"
                color="blue"
                loading={busyId === ws.id}
                disabled={busyId !== null}
                onClick={() => runAction(ws.id, (t) => syncAdminWorkspace(t, ws.id))}
              >
                <IconRefresh size={16} />
              </RowActionIcon>
              <RowActionIcon
                label="Remover workspace"
                color="red"
                disabled={busyId !== null}
                onClick={() => {
                  if (!window.confirm(`Remover o workspace ${ws.name}? Os repositórios do catálogo não são afetados.`)) return
                  runAction(ws.id, (t) => deleteAdminWorkspace(t, ws.id))
                }}
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
