import { apiFetch, formatApiErrorPayload } from './http'
import type { ConversationUsage } from './streamTypes'

// ── AI Models ────────────────────────────────────────────────────────────────

export type ModelTier = 'free' | 'paid' | 'unknown'

export interface AiModel {
  id: string
  provider_id: string
  model_id: string
  display_name: string
  capabilities: string[]
  is_default: Record<string, boolean>
  context_window: number
  /** Preço do prompt em USD por 1 milhão de tokens (null = desconhecido). */
  input_cost_per_1m_usd: number | null
  /** Preço do completion em USD por 1 milhão de tokens (null = desconhecido). */
  output_cost_per_1m_usd: number | null
  tier: ModelTier
  active: boolean
  created_at: string
}

export interface AiModelSyncResult {
  provider_id: string
  fetched: number
  created: number
  updated: number
  deactivated: number
}

export async function fetchAiModels(token: string): Promise<AiModel[]> {
  const res = await apiFetch('/api/ai-models', {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) return []
  return res.json()
}

/**
 * Dispara sync do catálogo OpenRouter → DB (cria/atualiza pricing dos modelos).
 */
export async function syncAiModelsFromOpenrouter(
  token: string,
): Promise<AiModelSyncResult> {
  const res = await apiFetch('/api/ai-models/sync-from-openrouter', {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || 'Falha ao sincronizar modelos')
  }
  return res.json()
}

/**
 * Totais agregados de tokens/custo de uma conversa.
 */
export async function fetchConversationUsage(
  token: string,
  conversationId: string,
): Promise<ConversationUsage> {
  const res = await apiFetch(`/api/conversations/${conversationId}/usage`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) {
    return { total_prompt_tokens: 0, total_completion_tokens: 0, total_cost_usd: 0 }
  }
  return res.json()
}

// ── Agent Tasks / Runs ──────────────────────────────────────────────────────

export interface AgentTask {
  id: string
  env_slug: string
  status: 'pending' | 'running' | 'paused' | 'done' | 'error' | string
  triggered_by: string
  prompt: string
  conversation_id: string | null
  started_at: string | null
  completed_at: string | null
  last_event_at: string | null
  created_at: string
}

export interface AgentTaskEvent {
  id: number
  event_type: string
  data: Record<string, unknown>
  created_at: string
}

/**
 * Lista execuções recentes do agente, com filtros opcionais por status e ambiente.
 */
export async function fetchAgentTasks(
  token: string,
  options: { status?: string; envSlug?: string; limit?: number } = {},
): Promise<AgentTask[]> {
  const params = new URLSearchParams()
  if (options.status) params.set('status', options.status)
  if (options.envSlug) params.set('env_slug', options.envSlug)
  if (options.limit) params.set('limit', String(options.limit))
  const suffix = params.toString() ? `?${params.toString()}` : ''
  const res = await apiFetch(`/api/tasks${suffix}`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) return []
  return res.json()
}

/**
 * Carrega eventos persistidos de uma execução do agente.
 */
export async function fetchAgentTaskEvents(
  token: string,
  taskId: string,
  options: { after?: number; limit?: number } = {},
): Promise<AgentTaskEvent[]> {
  const params = new URLSearchParams()
  if (options.after !== undefined) params.set('after', String(options.after))
  if (options.limit) params.set('limit', String(options.limit))
  const suffix = params.toString() ? `?${params.toString()}` : ''
  const res = await apiFetch(`/api/tasks/${encodeURIComponent(taskId)}/events${suffix}`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) throw new Error('Não foi possível carregar eventos da execução')
  return res.json()
}
