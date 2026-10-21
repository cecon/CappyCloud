import { ActionIcon, Badge, Menu, Table, Text } from '@/components/ui/legacy'
import {
  IconCopy,
  IconCpu,
  IconDotsVertical,
  IconPlayerPlay,
  IconPlayerStop,
  IconRefresh,
  IconSettings,
  IconTerminal2,
  IconTrash,
} from '@tabler/icons-react'
import type { Sandbox } from '../../api'
import { ActionsCell, ActionsHeader, RowActionIcon } from '../../components/TableActions'
import styles from '../AdminSandboxesPage.module.css'
import { isLiveStatus, STATUS_COLORS, STATUS_LABELS } from './constants'

type Props = {
  items: Sandbox[]
  pendingAction: string | null
  canUseTerminal: boolean
  onBoot: (sb: Sandbox) => void
  onStop: (sb: Sandbox) => void
  onDelete: (sb: Sandbox) => void
  onOpenGlobals: (sb: Sandbox, tab: 'claude' | 'runtime') => void
  onClone: (sb: Sandbox) => void
  onTerminal: (sb: Sandbox) => void
}

export function SandboxesTable({
  items,
  pendingAction,
  canUseTerminal,
  onBoot,
  onStop,
  onDelete,
  onOpenGlobals: openGlobals,
  onClone,
  onTerminal,
}: Props) {
  return (
    <Table verticalSpacing="sm" highlightOnHover>
      <Table.Thead>
        <Table.Tr>
          <Table.Th>Nome</Table.Th>
          <Table.Th style={{ width: 140 }}>Agente</Table.Th>
          <Table.Th>Imagem</Table.Th>
          <Table.Th style={{ width: 180 }}>Container</Table.Th>
          <Table.Th style={{ width: 120 }}>Sessões</Table.Th>
          <ActionsHeader width={132} />
        </Table.Tr>
      </Table.Thead>
      <Table.Tbody>
        {items.map((sb) => {
          const isPending = pendingAction === sb.id
          const containerExists = sb.container_status !== 'not_created'
          const live = isLiveStatus(sb.container_status)
          return (
            <Table.Tr key={sb.id} className={live ? styles.liveRow : undefined}>
              <Table.Td>
                <Text fw={600}>{sb.name}</Text>
                <Text size="xs" c="dimmed">
                  {sb.host}:{sb.grpc_port}/{sb.session_port}
                </Text>
              </Table.Td>
              <Table.Td>
                {/* Runtime do agente (clicável: abre a troca); o modo do container fica abaixo. */}
                <button
                  type="button"
                  onClick={() => openGlobals(sb, 'runtime')}
                  title="Trocar o runtime do agente (openclaude ou Claude CLI)"
                  style={{ background: 'none', border: 0, padding: 0, cursor: 'pointer' }}
                >
                  <Badge variant="light" color={sb.agent_runtime === 'claude_cli' ? 'orange' : 'blue'}>
                    {sb.agent_runtime === 'claude_cli' ? 'Claude CLI' : 'openclaude'}
                  </Badge>
                </button>
                <Text size="xs" c="dimmed">
                  {sb.runtime}
                </Text>
              </Table.Td>
              <Table.Td>
                <Text size="sm" style={{ wordBreak: 'break-all' }}>
                  {sb.image || <em style={{ opacity: 0.5 }}>(vazia)</em>}
                </Text>
              </Table.Td>
              <Table.Td>
                <Badge
                  color={STATUS_COLORS[sb.container_status]}
                  variant={sb.container_status === 'configured' ? 'filled' : 'light'}
                >
                  {STATUS_LABELS[sb.container_status]}
                </Badge>
              </Table.Td>
              <Table.Td>
                <Text size="sm" fw={600}>
                  {sb.active_sessions ?? 0}
                </Text>
              </Table.Td>
              <ActionsCell>
                <RowActionIcon
                  label={live ? 'Sincronizar e reiniciar OpenClaude' : 'Iniciar container'}
                  color={live ? 'yellow' : 'blue'}
                  onClick={() => onBoot(sb)}
                  loading={isPending}
                  disabled={isPending}
                >
                  {live ? <IconRefresh size={16} /> : <IconPlayerPlay size={16} />}
                </RowActionIcon>
                <RowActionIcon
                  label="Parar container"
                  color="gray"
                  variant="default"
                  onClick={() => onStop(sb)}
                  loading={isPending}
                  disabled={isPending || !live}
                >
                  <IconPlayerStop size={16} />
                </RowActionIcon>
                {canUseTerminal && (
                  <RowActionIcon
                    label={live ? 'Terminal (ex.: claude login)' : 'Terminal: inicie o container primeiro'}
                    color="grape"
                    variant="default"
                    onClick={() => onTerminal(sb)}
                    disabled={isPending || !live}
                  >
                    <IconTerminal2 size={16} />
                  </RowActionIcon>
                )}
                <Menu shadow="md" position="bottom-end">
                  <Menu.Target>
                    <ActionIcon
                      aria-label="Mais ações"
                      title="Mais ações"
                      variant="default"
                      size="lg"
                      disabled={isPending}
                    >
                      <IconDotsVertical size={16} />
                    </ActionIcon>
                  </Menu.Target>
                  <Menu.Dropdown>
                    <Menu.Item leftSection={<IconCpu size={14} />} onClick={() => openGlobals(sb, 'runtime')}>
                      Runtime do agente (openclaude / Claude CLI)...
                    </Menu.Item>
                    <Menu.Item leftSection={<IconSettings size={14} />} onClick={() => openGlobals(sb, 'claude')}>
                      CLAUDE.md, MCPs, Skills e Agents...
                    </Menu.Item>
                    <Menu.Item leftSection={<IconCopy size={14} />} onClick={() => onClone(sb)}>
                      Clonar
                    </Menu.Item>
                    <Menu.Item
                      color="red"
                      leftSection={<IconTrash size={14} />}
                      disabled={
                        containerExists &&
                        sb.container_status !== 'stopped' &&
                        sb.container_status !== 'error'
                      }
                      onClick={() => onDelete(sb)}
                    >
                      Apagar
                    </Menu.Item>
                  </Menu.Dropdown>
                </Menu>
              </ActionsCell>
            </Table.Tr>
          )
        })}
      </Table.Tbody>
    </Table>
  )
}
