import { useCallback, useEffect, useState } from 'react'
import { Alert, Button, Container, Group, Loader, Paper, Stack, Text, Title } from '@/components/ui/legacy'
import {
  type AdminUser,
  errorToUserMessage,
  fetchAdminUsers,
  fetchCurrentUser,
  getToken,
  registerRequest,
  resetAdminUserPassword,
  updateAdminUserRole,
  type UserRole,
} from '../api'
import { UserAccessDrawer } from '../components/UserAccessDrawer'
import { isPlausibleEmail } from '../validation'
import { CreateUserModal } from './admin-users/CreateUserModal'
import { type CreateFormState, EMPTY_FORM } from './admin-users/formState'
import { UsersTable } from './admin-users/UsersTable'

export function AdminUsersPage() {
  const [users, setUsers] = useState<AdminUser[] | null>(null)
  const [meId, setMeId] = useState<string | null>(null)
  const [meIsSuperAdmin, setMeIsSuperAdmin] = useState(false)
  const [actionNotice, setActionNotice] = useState<string | null>(null)
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
      setMeIsSuperAdmin(Boolean(me.is_super_admin))
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

  async function resetPassword(target: AdminUser) {
    const ok = window.confirm(
      `Redefinir a senha de ${target.email}?

A senha volta para a temporária padrão, vale por 24 horas e a pessoa terá que trocá-la no próximo acesso.`,
    )
    if (!ok) return
    const token = getToken()
    if (!token) return
    setPendingRoleChange(target.id)
    setActionError(null)
    setActionNotice(null)
    try {
      const updated = await resetAdminUserPassword(token, target.id)
      setUsers((prev) => (prev ? prev.map((u) => (u.id === updated.id ? updated : u)) : prev))
      setActionNotice(
        `Senha de ${target.email} redefinida. Vale por 24 horas; no próximo acesso a pessoa define uma senha nova.`,
      )
    } catch (err) {
      setActionError(errorToUserMessage(err))
    } finally {
      setPendingRoleChange(null)
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

        {actionNotice && (
          <Alert color="green" title="Pronto" withCloseButton onClose={() => setActionNotice(null)}>
            {actionNotice}
          </Alert>
        )}
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
            <UsersTable
              users={users}
              meId={meId}
              meIsSuperAdmin={meIsSuperAdmin}
              pendingRoleChange={pendingRoleChange}
              onAccess={setAccessTarget}
              onChangeRole={(u, role) => void changeRole(u, role)}
              onResetPassword={(u) => void resetPassword(u)}
            />
          )}
        </Paper>
      </Stack>

      <CreateUserModal
        opened={createOpen}
        form={form}
        setForm={setForm}
        formError={formError}
        creating={creating}
        onClose={() => setCreateOpen(false)}
        onCreate={() => void handleCreate()}
      />

      <UserAccessDrawer user={accessTarget} onClose={() => setAccessTarget(null)} />
    </Container>
  )
}
