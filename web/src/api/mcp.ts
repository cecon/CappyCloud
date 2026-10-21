import { apiFetch, formatApiErrorPayload } from './http'

// ── User · Repository MCP Servers ───────────────────────────────────────────

export interface UserMcpServer {
  id: string
  user_id: string
  repository_id: string
  name: string
  token_preview: string
  enabled: boolean
  created_at: string
  updated_at: string
  last_used_at: string | null
}

export interface UserMcpServerSecret extends UserMcpServer {
  token: string
}

export interface UserMcpServerPayload {
  name: string
  repository_id: string
  enabled: boolean
}

export async function fetchUserMcpServers(token: string): Promise<UserMcpServer[]> {
  const res = await apiFetch('/api/mcp-servers', {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || 'Falha ao listar MCP servers')
  }
  return res.json()
}

export async function createUserMcpServer(
  token: string,
  data: UserMcpServerPayload,
): Promise<UserMcpServerSecret> {
  const res = await apiFetch('/api/mcp-servers', {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || 'Falha ao criar MCP server')
  }
  return res.json()
}

export async function updateUserMcpServer(
  token: string,
  serverId: string,
  data: UserMcpServerPayload,
): Promise<UserMcpServer> {
  const res = await apiFetch(`/api/mcp-servers/${serverId}`, {
    method: 'PUT',
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || 'Falha ao atualizar MCP server')
  }
  return res.json()
}

export async function rotateUserMcpServerToken(
  token: string,
  serverId: string,
): Promise<UserMcpServerSecret> {
  const res = await apiFetch(`/api/mcp-servers/${serverId}/rotate-token`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || 'Falha ao rotacionar token MCP')
  }
  return res.json()
}

export async function deleteUserMcpServer(token: string, serverId: string): Promise<void> {
  const res = await apiFetch(`/api/mcp-servers/${serverId}`, {
    method: 'DELETE',
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok && res.status !== 204) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || 'Falha ao remover MCP server')
  }
}

// ── Admin · MCP Servers (por sandbox) ────────────────────────────────────────

export type McpServer = {
  id: string
  sandbox_id: string
  name: string
  command: string
  args: string[]
  env: Record<string, string>
  enabled: boolean
  created_at: string
  updated_at: string
}

export type McpServerCreate = {
  name: string
  command: string
  args?: string[]
  env?: Record<string, string>
  enabled?: boolean
}

export type McpServerUpdate = McpServerCreate

export async function fetchSandboxMcps(
  token: string,
  sandboxId: string,
): Promise<McpServer[]> {
  const res = await apiFetch(`/api/admin/sandboxes/${sandboxId}/mcps`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || 'Falha ao listar MCPs')
  }
  return res.json()
}

export async function createSandboxMcp(
  token: string,
  sandboxId: string,
  data: McpServerCreate,
): Promise<McpServer> {
  const res = await apiFetch(`/api/admin/sandboxes/${sandboxId}/mcps`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || 'Falha ao criar MCP')
  }
  return res.json()
}

export async function updateSandboxMcp(
  token: string,
  sandboxId: string,
  mcpId: string,
  data: McpServerUpdate,
): Promise<McpServer> {
  const res = await apiFetch(`/api/admin/sandboxes/${sandboxId}/mcps/${mcpId}`, {
    method: 'PUT',
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || 'Falha ao atualizar MCP')
  }
  return res.json()
}

export async function deleteSandboxMcp(
  token: string,
  sandboxId: string,
  mcpId: string,
): Promise<void> {
  const res = await apiFetch(`/api/admin/sandboxes/${sandboxId}/mcps/${mcpId}`, {
    method: 'DELETE',
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok && res.status !== 204) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || 'Falha ao eliminar MCP')
  }
}
