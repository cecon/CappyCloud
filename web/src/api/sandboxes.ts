import { apiFetch, formatApiErrorPayload } from './http'

// ── Sandboxes ────────────────────────────────────────────────────────────────

export type SandboxRuntime = 'compose' | 'swarm'

export type ContainerStatus =
  | 'not_created'
  | 'starting'
  | 'running'
  | 'configuring'
  | 'configured'
  | 'stopped'
  | 'error'

/** Runtime do agente na sandbox (`runtime` é o orquestrador compose/swarm). */
export type AgentRuntime = 'openclaude' | 'claude_cli'

export interface Sandbox {
  id: string
  name: string
  host: string
  grpc_port: number
  session_port: number
  status: string
  runtime: SandboxRuntime
  image: string
  claude_md?: string
  agent_runtime?: AgentRuntime
  env_vars: Record<string, string>
  container_status: ContainerStatus
  active_sessions: number
  created_at: string
}

export async function fetchSandboxes(token: string): Promise<Sandbox[]> {
  const res = await apiFetch('/api/sandboxes', {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) return []
  return res.json()
}

// ── Admin · Sandboxes ────────────────────────────────────────────────────────

export interface SandboxAdminCreate {
  name: string
  runtime: SandboxRuntime
  image: string
  claude_md?: string
  agent_runtime?: AgentRuntime
  env_vars?: Record<string, string>
  host?: string | null
  grpc_port?: number
  session_port?: number
}

export interface SandboxAdminUpdate {
  image?: string
  claude_md?: string
  agent_runtime?: AgentRuntime
  env_vars?: Record<string, string>
  host?: string
  grpc_port?: number
  session_port?: number
  status?: string
}

/** Lista todas as sandboxes cadastradas (admin only). */
export async function fetchAdminSandboxes(token: string): Promise<Sandbox[]> {
  const res = await apiFetch('/api/admin/sandboxes', {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || 'Falha ao listar sandboxes')
  }
  return (await res.json()) as Sandbox[]
}

export async function createAdminSandbox(
  token: string,
  data: SandboxAdminCreate,
): Promise<Sandbox> {
  const res = await apiFetch('/api/admin/sandboxes', {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || 'Falha ao criar sandbox')
  }
  return (await res.json()) as Sandbox
}

export async function updateAdminSandbox(
  token: string,
  sandboxId: string,
  data: SandboxAdminUpdate,
): Promise<Sandbox> {
  const res = await apiFetch(`/api/admin/sandboxes/${sandboxId}`, {
    method: 'PATCH',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || 'Falha ao atualizar sandbox')
  }
  return (await res.json()) as Sandbox
}

export async function deleteAdminSandbox(token: string, sandboxId: string): Promise<void> {
  const res = await apiFetch(`/api/admin/sandboxes/${sandboxId}`, {
    method: 'DELETE',
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok && res.status !== 204) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || 'Falha ao remover sandbox')
  }
}

export async function cloneAdminSandbox(
  token: string,
  sandboxId: string,
  newName: string,
): Promise<Sandbox> {
  const res = await apiFetch(`/api/admin/sandboxes/${sandboxId}/clone`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ new_name: newName }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || 'Falha ao clonar sandbox')
  }
  return (await res.json()) as Sandbox
}

export async function bootAdminSandbox(token: string, sandboxId: string): Promise<Sandbox> {
  const res = await apiFetch(`/api/admin/sandboxes/${sandboxId}/boot`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || 'Falha ao iniciar sandbox')
  }
  return (await res.json()) as Sandbox
}

export async function stopAdminSandbox(token: string, sandboxId: string): Promise<Sandbox> {
  const res = await apiFetch(`/api/admin/sandboxes/${sandboxId}/stop`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || 'Falha ao parar sandbox')
  }
  return (await res.json()) as Sandbox
}
