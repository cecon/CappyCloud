import type { Conversation } from '../../api'
import type { ThoughtStep } from '../../components/ThinkingStream'
import {
  HEAVY_TURN_COST_THRESHOLD_USD,
  HEAVY_TURN_PROMPT_TOKEN_THRESHOLD,
  HEAVY_TURN_TOOL_THRESHOLD,
} from './constants'
import type { ActivityTrace, SessionProgressAnchor, StreamToolStats } from './types'

export function fallbackReasonLabel(reason?: string): string {
  const normalized = (reason || '').replace(/[_-]+/g, ' ').trim()
  return normalized || 'runtime model changed'
}

export function incrementStreamToolStats(prev: StreamToolStats, toolName: string): StreamToolStats {
  const normalized = toolName.trim().toLowerCase()
  const broadSearches = normalized === 'grep' || normalized === 'glob' || normalized === 'find'
    ? prev.broadSearches + 1
    : prev.broadSearches
  return { total: prev.total + 1, broadSearches }
}

export function heavyUsageReason(
  promptTokens?: number | null,
  completionTokens?: number | null,
  costUsd?: number | null,
): string | null {
  const prompt = promptTokens ?? 0
  const completion = completionTokens ?? 0
  const cost = costUsd ?? 0
  if (prompt >= HEAVY_TURN_PROMPT_TOKEN_THRESHOLD) {
    return `${prompt.toLocaleString('pt-BR')} tokens de entrada nesta resposta`
  }
  if (cost >= HEAVY_TURN_COST_THRESHOLD_USD) {
    return `${formatCostUsd(cost)} nesta resposta`
  }
  if (prompt + completion >= HEAVY_TURN_PROMPT_TOKEN_THRESHOLD) {
    return `${(prompt + completion).toLocaleString('pt-BR')} tokens totais nesta resposta`
  }
  return null
}

export function heavyToolReason(stats: StreamToolStats): string | null {
  if (stats.total < HEAVY_TURN_TOOL_THRESHOLD) return null
  const searchDetail = stats.broadSearches > 0
    ? `, ${stats.broadSearches} de busca/listagem ampla`
    : ''
  return `${stats.total} ferramentas chamadas nesta rodada${searchDetail}`
}

/** Tempo sem eventos do stream ativo (0 quando não há stream). */
export function streamIdleMsSince(streaming: boolean, streamActivityAt: number | null): number {
  return streaming && streamActivityAt
    ? Math.max(0, Date.now() - streamActivityAt)
    : 0
}

export function userInitials(email?: string | null): string {
  if (!email) return 'CC'
  const [name] = email.split('@')
  const parts = name.split(/[._-]+/).filter(Boolean)
  if (parts.length >= 2) return `${parts[0][0]}${parts[1][0]}`.toUpperCase()
  return name.slice(0, 2).toUpperCase()
}

export function userRoleLabel(user: { role?: string; is_super_admin?: boolean } | null): string {
  if (!user) return 'Conta'
  if (user.is_super_admin) return 'Super admin'
  if (user.role === 'admin') return 'Administrador'
  return 'Usuário'
}

/**
 * Formata custo USD como "$0.0034" / "$1.20" / "free" / "—".
 * Sub-cêntimo recebe 4 casas para não colapsar a zero.
 */
export function formatCostUsd(value: number | null | undefined): string {
  if (value == null) return '—'
  if (value === 0) return 'free'
  if (value < 0.01) return `$${value.toFixed(4)}`
  return `$${value.toFixed(2)}`
}

export function formatByteSize(value: number): string {
  const bytes = Math.max(0, Math.round(value || 0))
  if (bytes < 1024) return `${bytes} B`
  const kb = bytes / 1024
  if (kb < 1024) return `${kb.toFixed(kb >= 10 ? 0 : 1)} KB`
  const mb = kb / 1024
  return `${mb.toFixed(mb >= 10 ? 0 : 1)} MB`
}

/**
 * UUID v4 com fallback. `randomId()` só existe em contextos seguros
 * (HTTPS ou localhost). Em http://<IP>:porta o método é `undefined` e o React
 * estoura. Estes IDs são apenas chave React / id local de mensagem — não
 * precisam de aleatoriedade criptográfica quando o fallback é usado.
 */
export function randomId(): string {
  const c = typeof crypto !== 'undefined' ? crypto : undefined
  if (c && typeof c.randomUUID === 'function') return c.randomUUID()
  if (c && typeof c.getRandomValues === 'function') {
    const b = c.getRandomValues(new Uint8Array(16))
    b[6] = (b[6] & 0x0f) | 0x40
    b[8] = (b[8] & 0x3f) | 0x80
    const h = Array.from(b, (x) => x.toString(16).padStart(2, '0')).join('')
    return `${h.slice(0, 8)}-${h.slice(8, 12)}-${h.slice(12, 16)}-${h.slice(16, 20)}-${h.slice(20)}`
  }
  return `id-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 11)}`
}

/** Agrupa conversas em Hoje / Ontem / Anteriores */
export function groupConversations(convs: Conversation[]): { label: string; items: Conversation[] }[] {
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime()
  const yesterday = today - 86_400_000

  const groups: Record<string, Conversation[]> = { Hoje: [], Ontem: [], Anteriores: [] }
  for (const c of convs) {
    const d = new Date(c.created_at ?? c.id).getTime()
    if (d >= today) groups.Hoje.push(c)
    else if (d >= yesterday) groups.Ontem.push(c)
    else groups.Anteriores.push(c)
  }
  return Object.entries(groups)
    .filter(([, items]) => items.length > 0)
    .map(([label, items]) => ({ label, items }))
}

export function updateActivityTrace(
  prev: Record<string, ActivityTrace>,
  anchor: SessionProgressAnchor | null,
  updater: (steps: ThoughtStep[]) => ThoughtStep[],
): Record<string, ActivityTrace> {
  if (!anchor) return prev
  const current = prev[anchor.id] ?? { content: anchor.content, steps: [], elapsedMs: 0 }
  return {
    ...prev,
    [anchor.id]: {
      ...current,
      content: anchor.content,
      steps: updater(current.steps),
    },
  }
}
