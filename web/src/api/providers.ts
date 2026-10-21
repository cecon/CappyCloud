import { apiFetch, formatApiErrorPayload } from './http'
import type { AiModel, AiModelSyncResult, ModelTier } from './models'

// ── Admin LLM catalog (ADR-006) ─────────────────────────────────────────────

export interface AdminAiProvider {
  id: string
  name: string
  base_url: string
  api_format: 'chat_completions' | 'responses'
  active: boolean
  last_synced_at: string | null
  models_count: number
  auth_state: 'configured' | 'missing-key' | 'inactive' | 'catalog-only' | string
  auth_label: string
  auth_next_action: string
}

export interface AdminProviderCreate {
  name: string
  base_url: string
  api_format?: 'chat_completions' | 'responses'
  api_key?: string
  model_id?: string
  display_name?: string
  capabilities?: string[]
  context_window?: number
  active?: boolean
  is_default_text?: boolean
  is_default_embedding?: boolean
}

export interface AdminProviderPatch {
  name?: string
  base_url?: string
  api_format?: 'chat_completions' | 'responses'
  api_key?: string
  active?: boolean
}

export async function fetchAdminProviders(token: string): Promise<AdminAiProvider[]> {
  const res = await apiFetch('/api/admin/providers', {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) return []
  return res.json()
}

export async function createAdminProvider(
  token: string,
  payload: AdminProviderCreate,
): Promise<AdminAiProvider> {
  const res = await apiFetch('/api/admin/providers', {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || 'Falha ao cadastrar provider')
  }
  return res.json()
}

export async function patchAdminProvider(
  token: string,
  providerId: string,
  payload: AdminProviderPatch,
): Promise<AdminAiProvider> {
  const res = await apiFetch(`/api/admin/providers/${providerId}`, {
    method: 'PATCH',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || 'Falha ao atualizar provider')
  }
  return res.json()
}

export async function syncAdminProvider(
  token: string,
  providerId: string,
): Promise<AiModelSyncResult> {
  const res = await apiFetch(`/api/admin/providers/${providerId}/sync`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || 'Falha ao sincronizar provider')
  }
  return res.json()
}

export interface AdminModelsFilter {
  provider_id?: string
  tier?: ModelTier
  only_active?: boolean
  include_inactive_providers?: boolean
}

export async function fetchAdminModels(
  token: string,
  filter: AdminModelsFilter = {},
): Promise<AiModel[]> {
  const params = new URLSearchParams()
  if (filter.provider_id) params.set('provider_id', filter.provider_id)
  if (filter.tier) params.set('tier', filter.tier)
  if (filter.only_active) params.set('only_active', 'true')
  if (filter.include_inactive_providers) params.set('include_inactive_providers', 'true')
  const qs = params.toString()
  const url = qs ? `/api/admin/models?${qs}` : '/api/admin/models'
  const res = await apiFetch(url, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) return []
  return res.json()
}

export interface AdminModelPatch {
  active?: boolean
  tier?: ModelTier
  capabilities?: string[]
  is_default_text?: boolean
  is_default_embedding?: boolean
}

export async function patchAdminModel(
  token: string,
  modelId: string,
  patch: AdminModelPatch,
): Promise<AiModel> {
  const res = await apiFetch(`/api/admin/models/${modelId}`, {
    method: 'PATCH',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(patch),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || 'Falha ao atualizar modelo')
  }
  return res.json()
}
