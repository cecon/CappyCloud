import { useCallback, useEffect, useState } from 'react'
import {
  ActionIcon,
  Alert,
  Badge,
  Button,
  Checkbox,
  Container,
  Group,
  Loader,
  Menu,
  Modal,
  PasswordInput,
  Paper,
  Select,
  Stack,
  Table,
  Text,
  TextInput,
  Title,
} from '@mantine/core'
import {
  IconDotsVertical,
  IconKey,
  IconShieldDown,
  IconShieldUp,
  IconUserCog,
} from '@tabler/icons-react'
import {
  type AdminUser,
  errorToUserMessage,
  fetchAdminUsers,
  fetchCurrentUser,
  getToken,
  registerRequest,
  updateAdminUserRole,
  type UserRole,
} from '../api'
import { ActionsCell, ActionsHeader } from '../components/TableActions'
import { UserAccessDrawer } from '../components/UserAccessDrawer'
import { isPlausibleEmail } from '../validation'

type CreateFormState = {
  email: string
  password: string
  role: UserRole
  mustChangePassword: boolean
}

const EMPTY_FORM: CreateFormState = {
  email: '',
  password: '',
  role: 'user',
  mustChangePassword: true,
}

export function AdminUsersPage() {
  const [users, setUsers] = useState<AdminUser[] | null>(null)
  const [meId, setMeId] = useState<string | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)

  const [createOpen, setCreateOpen] = useState(false)
  const [form, setForm] = useState<CreateFormState>(EMPTY_FORM)
  const [formError, setFormError] = useState<string | null>(null)
  const [creating, setCreating] = useState(false)

  const [pendingRoleChange, setPendingRoleChange] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [accessTarget, setAccessTarget] = useState<AdminUser | null>(null)

  const reload = useCallback(async () => {
    const token = getToken()
    if (!token) return
    try {
      const [me, list] = await Promise.all([fetchCurrentUser(token), fetchAdminUsers(token)])
      setMeId(me.id)
      setUsers(list)
      setLoadError(null)
    } catch (err) {
      setLoadError(errorToUserMessage(err))
    }
  }, [])

  useEffect(() => {
    void reload()
  }, [reload])

  async function handleCreate() {
    const token = getToken()
    if (!token) return
    const email = form.email.trim().toLowerCase()
    if (!isPlausibleEmail(email)) {
      setFormError('Email inválido. Use o formato nome@dominio.com.')
      return
    }
    if (form.password.length < 8) {
      setFormError('A password deve ter pelo menos 8 caracteres.')
      return
    }
    setCreating(true)
    setFormError(null)
    try {
      await registerRequest(token, email, form.password, form.role, form.mustChangePassword)
      setForm(EMPTY_FORM)
      setCreateOpen(false)
      await reload()
    } catch (err) {
      setFormError(errorToUserMessage(err))
    } finally {
      setCreating(false)
    }
  }

  async function changeRole(target: AdminUser, role: UserRole) {
    if (target.role === role) return
    const token = getToken()
    if (!token) return
    setPendingRoleChange(target.id)
    setActionError(null)
    try {
      const updated = await updateAdminUserRole(token, target.id, role)
      setUsers((prev) =>
        prev ? prev.map((u) => (u.id === updated.id ? updated : u)) : prev,
      )
    } catch (err) {
      setActionError(errorToUserMessage(err))
    } finally {
      setPendingRoleChange(null)
    }
  }

  return (
    <Container size="lg" py="xl">
      <Stack gap="lg">
        <Group justify="space-between" align="flex-end">
          <Stack gap={4}>
            <Title order={2}>Usuários</Title>
            <Text c="dimmed" size="sm">
              Cadastro de utilizadores da plataforma. Apenas ADMINs criam, promovem e rebaixam contas.
            </Text>
          </Stack>
          <Button
            onClick={() => {
              setForm(EMPTY_FORM)
              setFormError(null)
              setCreateOpen(true)
            }}
          >
            Novo utilizador
          </Button>
        </Group>

        {actionError && (
          <Alert color="red" title="Falha na ação" withCloseButton onClose={() => setActionError(null)}>
            {actionError}
          </Alert>
        )}

        <Paper withBorder p="md" radius="md">
          {loadError ? (
            <Alert color="red" title="Não foi possível carregar utilizadores">
              {loadError}
            </Alert>
          ) : users === null ? (
            <Group justify="center" py="xl">
              <Loader />
            </Group>
          ) : users.length === 0 ? (
            <Text c="dimmed" ta="center" py="xl">
              Nenhum utilizador cadastrado. Use “Novo utilizador” para criar o primeiro.
            </Text>
          ) : (
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
                          onClick={() => setAccessTarget(u)}
                          disabled={u.role === 'admin'}
                        >
                          {u.role === 'admin' ? 'Acesso total' : 'Acessos'}
                        </Button>
                        <Menu shadow="md" position="bottom-end">
                          <Menu.Target>
                            <ActionIcon
                              aria-label="Alterar papel"
                              title="Alterar papel"
                              size="lg"
                              variant="default"
                              loading={isPending}
                              disabled={isPending}
                            >
                              {isPending ? (
                                <IconDotsVertical size={16} />
                              ) : (
                                <IconUserCog size={16} />
                              )}
                            </ActionIcon>
                          </Menu.Target>
                          <Menu.Dropdown>
                            <Menu.Item
                              disabled={u.role === 'admin'}
                              leftSection={<IconShieldUp size={14} />}
                              onClick={() => void changeRole(u, 'admin')}
                            >
                              Promover a ADMIN
                            </Menu.Item>
                            <Menu.Item
                              disabled={u.role === 'user' || isSelf}
                              leftSection={<IconShieldDown size={14} />}
                              onClick={() => void changeRole(u, 'user')}
                            >
                              Rebaixar para USER
                              {isSelf && (
                                <Text size="xs" c="dimmed">
                                  bloqueado: você mesmo
                                </Text>
                              )}
                            </Menu.Item>
                          </Menu.Dropdown>
                        </Menu>
                      </ActionsCell>
                    </Table.Tr>
                  )
                })}
              </Table.Tbody>
            </Table>
          )}
        </Paper>
      </Stack>

      <Modal
        opened={createOpen}
        onClose={() => setCreateOpen(false)}
        title="Novo utilizador"
        centered
      >
        <Stack gap="md">
          {formError && (
            <Alert color="red" title="Não foi possível criar">
              {formError}
            </Alert>
          )}
          <TextInput
            label="Email"
            placeholder="nome@dominio.com"
            value={form.email}
            onChange={(e) => setForm({ ...form, email: e.currentTarget.value })}
            type="email"
            autoComplete="off"
            required
          />
          <PasswordInput
            label="Senha temporária"
            description="Mínimo 8 caracteres. Use uma senha provisória para o primeiro login."
            value={form.password}
            onChange={(e) => setForm({ ...form, password: e.currentTarget.value })}
            autoComplete="new-password"
            required
          />
          <Checkbox
            label="Exigir troca de senha no primeiro acesso"
            checked={form.mustChangePassword}
            onChange={(e) =>
              setForm({ ...form, mustChangePassword: e.currentTarget.checked })
            }
          />
          <Select
            label="Papel"
            data={[
              { value: 'user', label: 'USER — uso normal' },
              { value: 'admin', label: 'ADMIN — administração total' },
            ]}
            value={form.role}
            onChange={(value) => {
              if (value === 'admin' || value === 'user') {
                setForm({ ...form, role: value })
              }
            }}
            allowDeselect={false}
          />
          <Group justify="flex-end" mt="sm">
            <Button variant="default" onClick={() => setCreateOpen(false)} disabled={creating}>
              Cancelar
            </Button>
            <Button onClick={() => void handleCreate()} loading={creating}>
              Criar
            </Button>
          </Group>
        </Stack>
      </Modal>

      <UserAccessDrawer user={accessTarget} onClose={() => setAccessTarget(null)} />
    </Container>
  )
}
