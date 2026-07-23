import type { ChatMessage } from '../../api'

export type ChatNavigationMarkerKind =
  | 'user_request'
  | 'assistant_final'
  | 'result_block'
  | 'decision'
  | 'group'

export type ChatNavigationActor = 'user' | 'assistant' | 'system_context'

export type ChatNavigationMarker = {
  id: string
  targetId: string
  sourceMessageId?: string
  kind: ChatNavigationMarkerKind
  actor: ChatNavigationActor
  title: string
  preview: string
  priority: number
  order: number
  groupedCount?: number
}

export const CHAT_NAVIGATION_MIN_MARKERS = 2
const MAX_VISIBLE_MARKERS = 48
const PREVIEW_LIMIT = 116
const TITLE_LIMIT = 42

const hiddenContentPatterns = [
  /\b(redigido|restrito|restricted|redacted|deleted|removido)\b/i,
]

const resultPatterns = [
  /\b(editou|criou|alterou|arquivos?|files?|resultado|result|diff|pr #?\d+)\b/i,
  /\b(pnpm|npm|pytest|ruff|mypy|docker compose|build|lint)\b/i,
  /\b(erro|error|failed|falhou|falha)\b/i,
]

const decisionPatterns = [
  /\b(decis[aã]o|decidido|vamos fazer|ficou definido|recomendo|pr[oó]ximo passo)\b/i,
]

function compactWhitespace(value: string): string {
  return value.replace(/\s+/g, ' ').trim()
}

function boundedText(value: string, limit: number): string {
  const text = compactWhitespace(value)
  if (text.length <= limit) return text
  return `${text.slice(0, Math.max(0, limit - 1)).trimEnd()}…`
}

function safePreview(content: string): string | null {
  const text = compactWhitespace(content)
  if (!text) return null
  if (hiddenContentPatterns.some((pattern) => pattern.test(text))) return null
  return boundedText(text, PREVIEW_LIMIT)
}

function markerKindForMessage(message: ChatMessage): ChatNavigationMarkerKind {
  if (decisionPatterns.some((pattern) => pattern.test(message.content))) return 'decision'
  if (resultPatterns.some((pattern) => pattern.test(message.content))) return 'result_block'
  return message.role === 'user' ? 'user_request' : 'assistant_final'
}

function markerTitle(kind: ChatNavigationMarkerKind, preview: string): string {
  if (kind === 'user_request') return boundedText(preview, TITLE_LIMIT)
  if (kind === 'result_block') return 'Resultado ou arquivo'
  if (kind === 'decision') return 'Decisão'
  if (kind === 'group') return 'Grupo de marcos'
  return boundedText(preview, TITLE_LIMIT)
}

function markerPriority(kind: ChatNavigationMarkerKind): number {
  if (kind === 'user_request') return 100
  if (kind === 'decision') return 95
  if (kind === 'result_block') return 90
  if (kind === 'assistant_final') return 70
  return 50
}

function markerActor(role: string, kind: ChatNavigationMarkerKind): ChatNavigationActor {
  if (kind === 'result_block' || kind === 'decision') return 'system_context'
  return role === 'user' ? 'user' : 'assistant'
}

function buildMarker(message: ChatMessage, order: number): ChatNavigationMarker | null {
  if (message.role !== 'user' && message.role !== 'assistant') return null
  const preview = safePreview(message.content)
  if (!preview) return null
  const kind = markerKindForMessage(message)
  return {
    id: `message-${message.id}`,
    targetId: `message-${message.id}`,
    sourceMessageId: message.id,
    kind,
    actor: markerActor(message.role, kind),
    title: markerTitle(kind, preview),
    preview,
    priority: markerPriority(kind),
    order,
  }
}

function compactMarkers(markers: ChatNavigationMarker[]): ChatNavigationMarker[] {
  if (markers.length <= MAX_VISIBLE_MARKERS) return markers
  const keep = new Set<string>()
  markers.forEach((marker, index) => {
    if (marker.priority >= 90 || index === 0 || index === markers.length - 1) keep.add(marker.id)
  })
  const remainingSlots = Math.max(0, MAX_VISIBLE_MARKERS - keep.size)
  const assistantMarkers = markers.filter((marker) => marker.priority < 90)
  const step = remainingSlots > 0 ? Math.ceil(assistantMarkers.length / remainingSlots) : Infinity
  assistantMarkers.forEach((marker, index) => {
    if (index % step === 0) keep.add(marker.id)
  })
  return markers.filter((marker) => keep.has(marker.id))
}

export function deriveChatNavigationMarkers(messages: ChatMessage[]): ChatNavigationMarker[] {
  const markers = compactMarkers(messages.map(buildMarker).filter((marker): marker is ChatNavigationMarker => !!marker))
  return markers.length >= CHAT_NAVIGATION_MIN_MARKERS ? markers : []
}
