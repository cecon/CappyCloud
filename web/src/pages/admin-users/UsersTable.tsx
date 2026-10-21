import { ActionIcon, Badge, Button, Group, Menu, Table, Text } from '@/components/ui/legacy'
import {
  IconDotsVertical,
  IconKey,
  IconLockOpen,
  IconShieldDown,
  IconShieldUp,
  IconUserCog,
} from '@tabler/icons-react'
import type { AdminUser, UserRole } from '../../api'
import { ActionsCell, ActionsHeader } from '../../components/TableActions'

type Props = {
  users: AdminUser[]
  meId: string | null
  meIsSuperAdmin: boolean
  /** Admin de workspace: sem mudar papel; senha só de USER dos workspaces dele. */
  meIsWorkspaceAdmin?: boolean
  pendingRoleChange: string | null
  onAccess: (user: AdminUser) => void
  onChangeRole: (user: AdminUser, role: UserRole) => void
  onResetPassword: (user: AdminUser) => void
}

export function UsersTable({
  users,
  meId,
  meIsSuperAdmin,
  meIsWorkspaceAdmin = false,
  pendingRoleChange,
  onAccess,
  onChangeRole,
  onResetPassword,
}: Props) {
  return (
    <Table verticalSpacing="sm" highlightOnHover>
      <Table.Thead>
        <Table.Tr>
          <Table.Th>Email</Table.Th>
          <Table.Th style={{ width: 110 }}>Papel</Table.Th>
          <ActionsHeader width={180} />
        </Table.Tr>
      </Table.Thead>
      <Table.Tbody>
        {users.map((u) => {
          const isSelf = u.id === meId
          const isPending = pendingRoleChange === u.id
          return (
            <Table.Tr key={u.id}>
              <Table.Td>
                <Group gap="xs">
                  <Text>{u.email}</Text>
                  {isSelf && (
                    <Badge size="xs" variant="light" color="blue">
                      você
                    </Badge>
                  )}
                  {u.is_super_admin && (
                    <Badge size="xs" variant="filled" color="violet">
                      SUPER ADMIN
                    </Badge>
                  )}
                  {u.must_change_password && (
                    <Badge size="xs" variant="light" color="orange">
                      troca pendente
                    </Badge>
                  )}
                </Group>
              </Table.Td>
              <Table.Td>
                <Badge
                  color={u.role === 'admin' ? 'yellow' : 'gray'}
                  variant={u.role === 'admin' ? 'filled' : 'light'}
                >
                  {u.role === 'admin' ? 'ADMIN' : 'USER'}
                </Badge>
              </Table.Td>
              <ActionsCell>
                <Button
                  aria-label={u.role === 'admin' ? 'ADMIN tem acesso total' : 'Gerir acessos'}
                  title={u.role === 'admin' ? 'ADMIN tem acesso total' : 'Gerir acessos'}
                  size="xs"
                  variant="light"
                  color="blue"
                  leftSection={<IconKey size={14} />}
                  onClick={() => onAccess(u)}
                  disabled={u.role === 'admin'}
                >
                  {u.role === 'admin' ? 'Acesso total' : 'Acessos'}
                </Button>
                <Menu shadow="md" position="bottom-end">
                  <Menu.Target>
                    <ActionIcon
                      aria-label="Ações do usuário"
                      title="Papel e senha"
                      size="lg"
                      variant="default"
                      loading={isPending}
                      disabled={isPending}
                    >
                      {isPending ? <IconDotsVertical size={16} /> : <IconUserCog size={16} />}
                    </ActionIcon>
                  </Menu.Target>
                  <Menu.Dropdown>
                    {!meIsWorkspaceAdmin && (
                      <>
                        <Menu.Item
                          disabled={u.role === 'admin'}
                          leftSection={<IconShieldUp size={14} />}
                          onClick={() => onChangeRole(u, 'admin')}
                        >
                          Promover a ADMIN
                        </Menu.Item>
                        <Menu.Item
                          disabled={u.role === 'user' || isSelf}
                          leftSection={<IconShieldDown size={14} />}
                          onClick={() => onChangeRole(u, 'user')}
                        >
                          Rebaixar para USER
                          {isSelf && (
                            <Text size="xs" c="dimmed">
                              bloqueado: você mesmo
                            </Text>
                          )}
                        </Menu.Item>
                      </>
                    )}
                    {(meIsSuperAdmin || (meIsWorkspaceAdmin && u.role === 'user')) && !isSelf && (
                      <Menu.Item leftSection={<IconLockOpen size={14} />} onClick={() => onResetPassword(u)}>
                        Redefinir senha
                      </Menu.Item>
                    )}
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
