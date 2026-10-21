import { apiFetch } from './http'
import type { PermissionMode, RepoSelection } from './preferences'
import type { PayloadSizeBreakdown, PlanUsage } from './streamTypes'

export type Conversation = {
  id: string
  user_id?: string | null
  user_email?: string | null
  title: string
  created_at: string
  updated_at: string
  sandbox_id: string | null
  repos: RepoSelection[]
  session_root: string | null
  /** Conversa de workspace: abre todos os repositórios dele. */
  workspace_id?: string | null
  permission_mode: PermissionMode
  /** Arquivada: fora da lista padrão, mas continua aberta e intacta. */
  archived_at?: string | null
  /** Número do chamado (ex.: Zendesk) que originou a conversa. */
  ticket_number?: string | null
}

/** Workspace que o utilizador pode usar ao abrir uma conversa. */
export interface AccessibleWorkspace {
  id: string
  slug: string
  name: string
  sandbox_id: string
  /** Sandbox onde as conversas do workspace rodam. */
  sandbox_name?: string
  /** Sincronizado no sandbox e com repositórios. */
  ready: boolean
  /** Desligado, o chat não oferece o modo de planejamento neste workspace. */
  plan_mode_enabled?: boolean
  /** Conversa nova só abre com o número do chamado. */
  require_ticket?: boolean
  repositories: Array<{ alias: string; slug: string; read_only?: boolean }>
}

export async function fetchAccessibleWorkspaces(token: string): Promise<AccessibleWorkspace[]> {
  const res = await apiFetch('/api/workspaces/accessible', {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) return []
  return res.json()
}

/**
 * Workspaces para os filtros do admin: ADMIN vê todos; admin de workspace só
 * os que administra (`adminWorkspaceIds`), não os que só usa.
 */
export async function fetchAdminFilterWorkspaces(
  token: string,
  adminWorkspaceIds: string[] | null,
): Promise<AccessibleWorkspace[]> {
  const all = await fetchAccessibleWorkspaces(token)
  if (!adminWorkspaceIds) return all
  return all.filter((ws) => adminWorkspaceIds.includes(ws.id))
}

export type ChatMessage = {
  id: string
  role: string
  content: string
  created_at: string
  /** Modelo IA usado para gerar a resposta (apenas em mensagens do assistente). */
  model_used?: string | null
  prompt_tokens?: number
  completion_tokens?: number
  cost_usd?: number
  payload_diagnostics?: PayloadSizeBreakdown | null
  /** Claude CLI: uso das janelas da assinatura quando a resposta terminou. */
  plan_usage?: PlanUsage | null
}
