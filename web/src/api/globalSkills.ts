import { apiFetch, formatApiErrorPayload } from './http'

// ── Admin · Global Skills catalog ───────────────────────────────────────────

export interface GlobalSkill {
  id: string
  name: string
  description: string
  content: string
  enabled: boolean
  sandbox_ids: string[]
  created_at: string
  updated_at: string
}

export interface GlobalSkillPayload {
  name: string
  description?: string
  content?: string
  enabled?: boolean
  sandbox_ids: string[]
}

export async function fetchGlobalSkills(token: string): Promise<GlobalSkill[]> {
  const res = await apiFetch('/api/admin/global-skills', {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || 'Falha ao listar skills globais')
  }
  return res.json()
}

export async function createGlobalSkill(
  token: string,
  data: GlobalSkillPayload,
): Promise<GlobalSkill> {
  const res = await apiFetch('/api/admin/global-skills', {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || 'Falha ao criar skill global')
  }
  return res.json()
}

export async function updateGlobalSkill(
  token: string,
  skillId: string,
  data: GlobalSkillPayload,
): Promise<GlobalSkill> {
  const res = await apiFetch(`/api/admin/global-skills/${skillId}`, {
    method: 'PUT',
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || 'Falha ao atualizar skill global')
  }
  return res.json()
}

export async function deleteGlobalSkill(token: string, skillId: string): Promise<void> {
  const res = await apiFetch(`/api/admin/global-skills/${skillId}`, {
    method: 'DELETE',
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok && res.status !== 204) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || 'Falha ao eliminar skill global')
  }
}

// ── Admin · Sandbox Skills (projecao das globais por sandbox) ────────────────

export interface SandboxSkill {
  id: string
  sandbox_id: string
  name: string
  description: string
  content: string
  enabled: boolean
  created_at: string
  updated_at: string
}

export interface SandboxSkillPayload {
  name: string
  description?: string
  content?: string
  enabled?: boolean
}

export async function fetchSandboxSkills(
  token: string,
  sandboxId: string,
): Promise<SandboxSkill[]> {
  const res = await apiFetch(`/api/admin/sandboxes/${sandboxId}/skills`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || 'Falha ao listar skills')
  }
  return res.json()
}

export async function createSandboxSkill(
  token: string,
  sandboxId: string,
  data: SandboxSkillPayload,
): Promise<SandboxSkill> {
  const res = await apiFetch(`/api/admin/sandboxes/${sandboxId}/skills`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || 'Falha ao criar skill')
  }
  return res.json()
}

export async function updateSandboxSkill(
  token: string,
  sandboxId: string,
  skillId: string,
  data: SandboxSkillPayload,
): Promise<SandboxSkill> {
  const res = await apiFetch(`/api/admin/sandboxes/${sandboxId}/skills/${skillId}`, {
    method: 'PUT',
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || 'Falha ao atualizar skill')
  }
  return res.json()
}

export async function deleteSandboxSkill(
  token: string,
  sandboxId: string,
  skillId: string,
): Promise<void> {
  const res = await apiFetch(`/api/admin/sandboxes/${sandboxId}/skills/${skillId}`, {
    method: 'DELETE',
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok && res.status !== 204) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || 'Falha ao eliminar skill')
  }
}
