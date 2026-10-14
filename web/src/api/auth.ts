import { apiFetch, formatApiErrorPayload } from './http'

export async function loginRequest(email: string, password: string): Promise<string> {
  const body = new URLSearchParams()
  body.set('username', email)
  body.set('password', password)
  const res = await fetch('/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: body.toString(),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    const text = formatApiErrorPayload(err) || 'Falha no login'
    throw new Error(String(text))
  }
  const data = (await res.json()) as { access_token: string }
  return data.access_token
}

export type UserRole = 'admin' | 'user'

export interface CurrentUser {
  id: string
  email: string
  role: UserRole
  is_super_admin: boolean
  must_change_password: boolean
}

/**
 * Cria um novo utilizador. Apenas ADMINs autenticados podem chamar
 * (ADR-005). O parâmetro {@link token} é o JWT do admin solicitante.
 */
export async function registerRequest(
  token: string,
  email: string,
  password: string,
  role: UserRole = 'user',
  mustChangePassword = true,
): Promise<CurrentUser> {
  const payload = {
    email: String(email ?? '')
      .trim()
      .toLowerCase(),
    password: String(password ?? ''),
    role,
    must_change_password: mustChangePassword,
  }
  const res = await apiFetch('/api/auth/register', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json; charset=utf-8',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    const text = formatApiErrorPayload(err) || 'Falha ao criar utilizador'
    throw new Error(String(text))
  }
  return (await res.json()) as CurrentUser
}

/**
 * Devolve o utilizador autenticado (com {@link UserRole}). O frontend usa
 * isto após login para decidir a navegação admin (ADR-005).
 */
export async function fetchCurrentUser(token: string): Promise<CurrentUser> {
  const res = await apiFetch('/api/auth/me', {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) {
    throw new Error('Não foi possível carregar utilizador')
  }
  return (await res.json()) as CurrentUser
}

export async function changePasswordRequest(
  token: string,
  currentPassword: string,
  newPassword: string,
): Promise<CurrentUser> {
  const res = await apiFetch('/api/auth/change-password', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json; charset=utf-8',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({
      current_password: currentPassword,
      new_password: newPassword,
    }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    const text = formatApiErrorPayload(err) || 'Falha ao alterar senha'
    throw new Error(String(text))
  }
  return (await res.json()) as CurrentUser
}

// ── Admin · Users ────────────────────────────────────────────────────────────

export interface AdminUser {
  id: string
  email: string
  role: UserRole
  is_super_admin: boolean
  must_change_password: boolean
}

/** Lista todos os utilizadores (admin only). */
/** Volta a senha para a temporária padrão (vale 24 h) e obriga a troca. Só super admin. */
export async function resetAdminUserPassword(token: string, userId: string): Promise<AdminUser> {
  const res = await apiFetch(`/api/admin/users/${userId}/reset-password`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || 'Falha ao redefinir a senha')
  }
  return (await res.json()) as AdminUser
}

export async function fetchAdminUsers(token: string): Promise<AdminUser[]> {
  const res = await apiFetch('/api/admin/users', {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || 'Falha ao listar utilizadores')
  }
  return (await res.json()) as AdminUser[]
}

/** Altera o papel de um utilizador (admin only). */
export async function updateAdminUserRole(
  token: string,
  userId: string,
  role: UserRole,
): Promise<AdminUser> {
  const res = await apiFetch(`/api/admin/users/${userId}/role`, {
    method: 'PATCH',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ role }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || 'Falha ao alterar papel')
  }
  return (await res.json()) as AdminUser
}
