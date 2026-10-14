import type { ContextProgressEvent, DoneEvent, PayloadSizeBreakdown, PayloadSizeCategory, RuntimeStateEvent, RuntimeStateKind, StatusEvent, SubagentActivityEvent, SubagentActivityState, SubagentGroupEvent } from './streamTypes'

const PAYLOAD_CATEGORY_LABELS: Record<string, string> = {
  user_message: 'Mensagem do usuario',
  conversation_history: 'Historico da conversa',
  repository_context: 'Contexto do repositorio',
  attachments: 'Anexos',
  tool_results: 'Resultados de ferramentas',
  tool_schemas: 'Ferramentas',
  mcp_tool_schemas: 'Ferramentas MCP',
  runtime_context: 'Contexto de runtime',
  other: 'Outros',
}

export function parsePayloadDiagnostics(value: unknown): PayloadSizeBreakdown | null {
  if (!value || typeof value !== 'object') return null
  const raw = value as Record<string, unknown>
  const rawCategories = Array.isArray(raw.categories) ? raw.categories : []
  const categoriesByKey = new Map<string, PayloadSizeCategory>()

  for (const item of rawCategories) {
    if (!item || typeof item !== 'object') continue
    const record = item as Record<string, unknown>
    const key = typeof record.key === 'string' && record.key in PAYLOAD_CATEGORY_LABELS
      ? record.key
      : 'other'
    const size = safeByteCount(record.size_bytes)
    if (size <= 0) continue
    const current = categoriesByKey.get(key)
    if (current) {
      current.size_bytes += size
    } else {
      categoriesByKey.set(key, {
        key,
        label: PAYLOAD_CATEGORY_LABELS[key],
        size_bytes: size,
        percentage: 0,
      })
    }
  }

  const categories = [...categoriesByKey.values()].sort((a, b) => b.size_bytes - a.size_bytes)
  const total = categories.length
    ? categories.reduce((sum, category) => sum + category.size_bytes, 0)
    : safeByteCount(raw.total_size_bytes)
  if (total <= 0) return null
  for (const category of categories) {
    category.percentage = Math.round((category.size_bytes / total) * 1000) / 10
  }

  return {
    total_size_bytes: total,
    categories,
    source: safeDiagnosticSource(raw.source),
    generated_at: safeDiagnosticText(raw.generated_at),
  }
}

function safeByteCount(value: unknown): number {
  const numeric = typeof value === 'number' ? value : Number(value)
  return Number.isFinite(numeric) ? Math.max(0, Math.round(numeric)) : 0
}

function safeDiagnosticSource(value: unknown): string {
  const source = typeof value === 'string' ? value.trim().toLowerCase() : 'openclaude'
  return source === 'openclaude' || source === 'cappycloud' || source === 'agent'
    ? source
    : 'openclaude'
}

function safeDiagnosticText(value: unknown): string {
  const text = typeof value === 'string' ? value.trim() : ''
  return /^[A-Za-z0-9_.:+-]{1,64}$/.test(text) ? text : ''
}

function parseStatusMetadata(value: unknown): StatusEvent['metadata'] | undefined {
  if (!value || typeof value !== 'object') return undefined
  const durationMs = (value as Record<string, unknown>).duration_ms
  const warning = safePermissionWarningMetadata(value)
  if (typeof durationMs !== 'number') return warning
  return { ...warning, duration_ms: durationMs }
}

/** Converte um evento `status` cru (SSE ou histórico) no formato tipado. */
export function parseStatusEvent(evt: Record<string, unknown>): StatusEvent {
  const stage = evt.stage
  const mode = evt.mode
  return {
    message: (evt.message as string) ?? 'Preparando sessão...',
    stage: stage === 'workspace' || stage === 'context' || stage === 'agent' ? stage : undefined,
    mode: mode === 'initializing' || mode === 'resuming' ? mode : undefined,
    state: evt.state === 'active' || evt.state === 'done' ? evt.state : undefined,
    metadata: parseStatusMetadata(evt.metadata),
  }
}

function safePermissionWarningMetadata(value: unknown): StatusEvent['metadata'] | undefined {
  if (!value || typeof value !== 'object') return undefined
  const metadata = value as Record<string, unknown>
  const warning = metadata.permission_warning
  if (!warning || typeof warning !== 'object') return undefined
  const warningRecord = warning as Record<string, unknown>
  const runtimeConfirmed = warningRecord.runtime_confirmed === true
  const source = warningRecord.source === 'openclaude_startup_alert'
    ? 'openclaude_startup_alert'
    : null
  if (!runtimeConfirmed || source === null) return undefined
  return {
    permission_warning: {
      runtime_confirmed: true,
      source,
    },
  }
}

export function parseFallbackNotice(value: unknown): DoneEvent['fallback'] {
  if (!value || typeof value !== 'object') return null
  const record = value as Record<string, unknown>
  const selectedModel = safeModelText(record.selected_model)
  const finalModel = safeModelText(record.final_model)
  const reason = safeDiagnosticText(record.reason)
  if (!selectedModel || !finalModel || selectedModel === finalModel) return null
  return {
    selected_model: selectedModel,
    final_model: finalModel,
    reason: reason || 'runtime_model_changed',
  }
}

function safeModelText(value: unknown): string {
  const text = typeof value === 'string' ? value.trim() : ''
  return /^[A-Za-z0-9_.:/@+-]{1,256}$/.test(text) ? text : ''
}

export function parseContextProgress(evt: Record<string, unknown>): ContextProgressEvent {
  const percent = safeOptionalPercent(evt.percent)
  return {
    label: safeUserLabel(evt.label, 'Processando contexto'),
    current_value: safeOptionalCount(evt.current_value),
    limit_value: safeOptionalCount(evt.limit_value),
    percent,
    financial: false,
  }
}

export function parseSubagentGroup(evt: Record<string, unknown>): SubagentGroupEvent {
  const rawActivities = Array.isArray(evt.activities) ? evt.activities : []
  return {
    parent_turn_id: safeNullableId(evt.parent_turn_id),
    label: safeUserLabel(evt.label, 'Atividade auxiliar'),
    collapsible: evt.collapsible !== false,
    activities: rawActivities
      .filter((item): item is Record<string, unknown> => !!item && typeof item === 'object')
      .map(parseSubagentActivity),
  }
}

function parseSubagentActivity(item: Record<string, unknown>): SubagentActivityEvent {
  return {
    id: safeNullableId(item.id) ?? 'subagent',
    name: safeUserLabel(item.name, 'Subagente'),
    state: safeSubagentState(item.state),
    detail: safeUserLabel(item.detail, ''),
  }
}

function safeOptionalCount(value: unknown): number | null {
  if (value === null || value === undefined || value === '') return null
  const numeric = typeof value === 'number' ? value : Number(value)
  return Number.isFinite(numeric) ? Math.max(0, Math.round(numeric)) : null
}

function safeOptionalPercent(value: unknown): number | null {
  const numeric = safeOptionalCount(value)
  if (numeric === null) return null
  return Math.min(100, Math.max(0, numeric))
}

function safeNullableId(value: unknown): string | null {
  const text = typeof value === 'string' ? value.trim() : ''
  return /^[A-Za-z0-9_.:@+-]{1,256}$/.test(text) ? text : null
}

function safeUserLabel(value: unknown, fallback: string): string {
  const text = typeof value === 'string' ? value.trim() : ''
  if (!text) return fallback
  return text.replace(/[\r\n\t]+/g, ' ').slice(0, 280)
}

function safeSubagentState(value: unknown): SubagentActivityState {
  const state = typeof value === 'string' ? value : ''
  return state === 'loading' ||
    state === 'streaming' ||
    state === 'tool-running' ||
    state === 'permission-request' ||
    state === 'permission-timeout' ||
    state === 'stalled' ||
    state === 'canceled' ||
    state === 'failed' ||
    state === 'done'
    ? state
    : 'tool-running'
}

export function parseRuntimeState(evt: Record<string, unknown>, fallback: RuntimeStateKind): RuntimeStateEvent {
  const state = safeRuntimeState(evt.state ?? evt.type, fallback)
  return {
    state,
    label: safeUserLabel(evt.label, runtimeStateLabel(state)),
    detail: safeUserLabel(evt.detail ?? evt.message, ''),
    terminal: state === 'permission-timeout' || state === 'canceled' || state === 'failed' || state === 'done',
  }
}

function safeRuntimeState(value: unknown, fallback: RuntimeStateKind): RuntimeStateKind {
  const text = typeof value === 'string' ? value : ''
  return text === 'permission-timeout' ||
    text === 'stalled' ||
    text === 'canceled' ||
    text === 'failed' ||
    text === 'done'
    ? text
    : fallback
}

function runtimeStateLabel(state: RuntimeStateKind): string {
  switch (state) {
    case 'permission-timeout':
      return 'Permissão expirou'
    case 'stalled':
      return 'Execução sem novos eventos'
    case 'canceled':
      return 'Execução cancelada'
    case 'failed':
      return 'Execução falhou'
    case 'done':
      return 'Execução concluída'
  }
}
