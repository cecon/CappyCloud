import type { UserMcpServerPayload } from '../../api'
import type { McpServerFormState } from '../../components/McpServerFormModal'

export type SecretState = {
  serverId: string
  serverName: string
  token: string
}

export const EMPTY_FORM: McpServerFormState = { name: '', repository_id: '', enabled: true }
export const PUBLIC_BASE_KEY = 'cappycloud_mcp_public_base_url'

export function isLocalUrl(value: string): boolean {
  try {
    const host = new URL(value).hostname
    return ['localhost', '127.0.0.1', '::1'].includes(host)
  } catch {
    return false
  }
}

export function normaliseBaseUrl(value: string): string {
  return value.trim().replace(/\/+$/, '')
}

export function endpointUrl(serverId: string, publicBaseUrl: string): string {
  const base = normaliseBaseUrl(publicBaseUrl) || window.location.origin
  return `${base}/api/mcp/servers/${serverId}`
}

export function fallbackEndpointUrl(serverId: string, publicBaseUrl: string, token: string): string {
  const base = normaliseBaseUrl(publicBaseUrl) || window.location.origin
  return `${base}/api/mcp/token/${encodeURIComponent(token)}/servers/${serverId}`
}

export function staticClientId(serverId: string): string {
  return serverId
}

export function payloadFromForm(form: McpServerFormState): UserMcpServerPayload {
  return {
    name: form.name.trim(),
    repository_id: form.repository_id,
    enabled: form.enabled,
  }
}
