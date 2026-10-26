import type { PayloadSizeBreakdown, PlanUsage } from './streamTypes'
import { apiFetch, formatApiErrorPayload } from './http'

// -- Admin · Dashboard -----------------------------------------------------

export interface AdminDashboardTotals {
  users: number
  admins: number
  conversations: number
  conversations_24h: number
  messages: number
  assistant_messages: number
  running_tasks: number
  failed_tasks_24h: number
  open_pull_requests: number
  sandboxes: number
  active_sandboxes: number
  prompt_tokens: number
  completion_tokens: number
  total_cost_usd: number
}

export interface AdminDashboardConversation {
  id: string
  title: string
  user_id: string
  user_email: string | null
  sandbox_id: string | null
  created_at: string
  updated_at: string
  last_message_at: string | null
  last_message_preview: string | null
  model_used: string | null
  message_count: number
  cost_usd: number
  ci_status: string
  pr_status: string
}

/** Custo real registrado nas mensagens dos últimos `days` dias. */
export interface AdminDashboardCostPeriod {
  days: number
  cost_usd: number
  prompt_tokens: number
  completion_tokens: number
  conversations: number
}

export interface AdminDashboard {
  generated_at: string
  workspace_id: string | null
  totals: AdminDashboardTotals
  cost_periods: AdminDashboardCostPeriod[]
  recent_conversations: AdminDashboardConversation[]
}

// ── Admin · Conversas (leitura de qualquer conversa) ─────────────────────────

export interface AdminConversationItem {
  id: string
  title: string
  user_email: string | null
  workspace_slug: string | null
  workspace_name: string | null
  ticket_number: string | null
  created_at: string
  last_message_at: string | null
  questions: number
  message_count: number
  cost_usd: number
  pr_url: string | null
  archived: boolean
}

export interface AdminConversationMessage {
  id: string
  role: string
  content: string
  created_at: string
  model_used: string | null
  prompt_tokens: number
  completion_tokens: number
  cost_usd: number
  plan_usage?: PlanUsage | null
  payload_diagnostics?: PayloadSizeBreakdown | null
}

export interface AdminConversationDetail extends AdminConversationItem {
  messages: AdminConversationMessage[]
}

export async function fetchAdminConversations(
  token: string,
  filters: { q?: string; workspaceId?: string; limit?: number; offset?: number } = {},
): Promise<{ total: number; items: AdminConversationItem[] }> {
  const params = new URLSearchParams()
  if (filters.q) params.set('q', filters.q)
  if (filters.workspaceId) params.set('workspace_id', filters.workspaceId)
  params.set('limit', String(filters.limit ?? 50))
  params.set('offset', String(filters.offset ?? 0))
  const res = await apiFetch(`/api/admin/conversations?${params.toString()}`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || 'Falha ao listar conversas')
  }
  return res.json()
}

export async function fetchAdminConversation(token: string, id: string): Promise<AdminConversationDetail> {
  const res = await apiFetch(`/api/admin/conversations/${encodeURIComponent(id)}`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || 'Falha ao abrir a conversa')
  }
  return res.json()
}

export async function fetchAdminDashboard(
  token: string,
  opts: { limit?: number; workspaceId?: string } = {},
): Promise<AdminDashboard> {
  const params = new URLSearchParams()
  params.set('limit', String(opts.limit ?? 12))
  if (opts.workspaceId) params.set('workspace_id', opts.workspaceId)
  const res = await apiFetch(`/api/admin/dashboard?${params.toString()}`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || 'Falha ao carregar dashboard admin')
  }
  return (await res.json()) as AdminDashboard
}
