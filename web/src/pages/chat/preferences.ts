import type { AccessibleWorkspace, AiModel } from '../../api'
import { CHAT_PREFS_KEY, LAST_WORKSPACE_KEY } from './constants'
import type { ChatPreferenceState } from './types'

/**
 * Ordena modelos: free primeiro (melhor para experimentar), depois por preço de
 * input ascendente, com pricing desconhecido no fim. Estável por display_name.
 */
export function sortModelsForSelect(models: AiModel[]): AiModel[] {
  const score = (m: AiModel) => {
    const ic = m.input_cost_per_1m_usd
    if (ic == null) return Number.POSITIVE_INFINITY
    return Number(ic)
  }
  return [...models].sort((a, b) => {
    const sa = score(a)
    const sb = score(b)
    if (sa !== sb) return sa - sb
    return a.display_name.localeCompare(b.display_name)
  })
}

export function readChatPrefs(): ChatPreferenceState {
  try {
    const raw = window.localStorage.getItem(CHAT_PREFS_KEY)
    if (!raw) return {}
    const parsed = JSON.parse(raw)
    return parsed && typeof parsed === 'object' ? parsed : {}
  } catch {
    return {}
  }
}

export function updateChatPrefs(update: (prefs: ChatPreferenceState) => ChatPreferenceState): void {
  try {
    const next = update(readChatPrefs())
    window.localStorage.setItem(CHAT_PREFS_KEY, JSON.stringify(next))
  } catch {
    // Preferência local não deve bloquear o chat.
  }
}

export function defaultTextModelId(models: AiModel[]): string {
  return models.find((m) => m.is_default?.text)?.model_id || models[0]?.model_id || ''
}

export function validModelId(models: AiModel[], modelId?: string): string {
  if (!modelId) return ''
  return models.some((model) => model.model_id === modelId) ? modelId : ''
}

/** Workspace da nova conversa: o atual se ainda existir, o último usado, ou o primeiro pronto. */
export function defaultWorkspaceId(list: AccessibleWorkspace[], current: string): string {
  if (current && list.some((workspace) => workspace.id === current)) return current
  let remembered = ''
  try {
    remembered = localStorage.getItem(LAST_WORKSPACE_KEY) ?? ''
  } catch {
    remembered = ''
  }
  const usable = (id: string) => list.some((workspace) => workspace.id === id && workspace.ready)
  if (usable(remembered)) return remembered
  return (list.find((workspace) => workspace.ready) ?? list[0])?.id ?? ''
}

export function rememberWorkspace(id: string) {
  try {
    if (id) localStorage.setItem(LAST_WORKSPACE_KEY, id)
  } catch {
    // Sem storage (aba privada): só não lembra a escolha.
  }
}
