import type { AdminAiProvider, ProviderApiFormat } from '../../api'

export function formatTimestamp(iso: string | null): string {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleString('pt-PT')
  } catch {
    return iso
  }
}

export function authStateColor(state: AdminAiProvider['auth_state']): string {
  if (state === 'configured') return 'green'
  if (state === 'catalog-only') return 'blue'
  if (state === 'inactive') return 'gray'
  return 'yellow'
}

export type ProviderFormState = {
  name: string
  base_url: string
  api_format: ProviderApiFormat
  api_key: string
  model_id: string
  display_name: string
  context_window: number
  capabilities: string[]
  active: boolean
  is_default_text: boolean
  is_default_embedding: boolean
}

export const EMPTY_FORM: ProviderFormState = {
  name: '',
  base_url: '',
  api_format: 'chat_completions',
  api_key: '',
  model_id: '',
  display_name: '',
  context_window: 200000,
  capabilities: ['text'],
  active: true,
  is_default_text: false,
  is_default_embedding: false,
}

export function formFromProvider(provider: AdminAiProvider): ProviderFormState {
  return {
    ...EMPTY_FORM,
    name: provider.name,
    base_url: provider.base_url,
    api_format: provider.api_format,
    active: provider.active,
  }
}
