import { apiFetch, formatApiErrorPayload } from './http'

// ── Admin · Sandbox Agents (subagents globais por sandbox) ───────────────────

export interface SandboxAgent {
  id: string
  sandbox_id: string
  name: string
  description: string
  system_prompt: string
  model: string
  tools: string[]
  enabled: boolean
  created_at: string
  updated_at: string
}

export interface SandboxAgentPayload {
  name: string
  description?: string
  system_prompt?: string
  model?: string
  tools?: string[]
  enabled?: boolean
}

export async function fetchSandboxAgents(
  token: string,
  sandboxId: string,
): Promise<SandboxAgent[]> {
  const res = await apiFetch(`/api/admin/sandboxes/${sandboxId}/agents`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || 'Falha ao listar agents')
  }
  return res.json()
}

export async function createSandboxAgent(
  token: string,
  sandboxId: string,
  data: SandboxAgentPayload,
): Promise<SandboxAgent> {
  const res = await apiFetch(`/api/admin/sandboxes/${sandboxId}/agents`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || 'Falha ao criar agent')
  }
  return res.json()
}

export async function updateSandboxAgent(
  token: string,
  sandboxId: string,
  agentId: string,
  data: SandboxAgentPayload,
): Promise<SandboxAgent> {
  const res = await apiFetch(`/api/admin/sandboxes/${sandboxId}/agents/${agentId}`, {
    method: 'PUT',
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || 'Falha ao atualizar agent')
  }
  return res.json()
}

export async function deleteSandboxAgent(
  token: string,
  sandboxId: string,
  agentId: string,
): Promise<void> {
  const res = await apiFetch(`/api/admin/sandboxes/${sandboxId}/agents/${agentId}`, {
    method: 'DELETE',
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok && res.status !== 204) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || 'Falha ao eliminar agent')
  }
}
