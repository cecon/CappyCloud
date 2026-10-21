/** Janela de uso da assinatura do Claude (`claude login`). */
export type PlanUsageWindow = { used_pct: number | null; resets_at: string | null }

export type PlanUsage = {
  status?: string | null
  five_hour?: PlanUsageWindow
  seven_day?: PlanUsageWindow
}

export type PayloadSizeCategory = {
  key: string
  label: string
  size_bytes: number
  percentage?: number | null
}

export type PayloadSizeBreakdown = {
  total_size_bytes: number
  categories: PayloadSizeCategory[]
  source?: string | null
  generated_at?: string | null
}

export interface ConversationUsage {
  total_prompt_tokens: number
  total_completion_tokens: number
  total_cost_usd: number
}

export interface DoneEvent {
  model_used: string | null
  prompt_tokens: number
  completion_tokens: number
  plan_usage?: PlanUsage | null
  fallback?: {
    selected_model?: string
    final_model?: string
    reason?: string
  } | null
}

export interface ToolStartEvent {
  name: string
  input: string
  id: string
}

export interface ToolResultEvent {
  name: string
  output: string
  is_error: boolean
  id: string
}

export interface CommandStartEvent {
  command: string
  label: string
}

export type CommandResultStatus =
  | 'started'
  | 'waiting_for_input'
  | 'completed'
  | 'unavailable'
  | 'failed'
  | 'cancelled'

export interface CommandResultEvent {
  command: string
  status: CommandResultStatus
  summary: string
  details_markdown?: string | null
}

export interface ActionRequiredEvent {
  prompt_id: string
  question: string
  action_type: number // 0 = confirm (sim/não), 1 = request_info (choices ou free-text)
  choices: string[] | null
}

/**
 * Fases reais de um turno emitidas pelo backend: workspace (clone/worktree na
 * primeira mensagem), context (montagem do prompt) e agent (espera do modelo).
 */
export type TurnPhaseStage = 'workspace' | 'context' | 'agent'

export interface StatusEvent {
  message: string
  stage?: TurnPhaseStage
  mode?: 'initializing' | 'resuming'
  state?: 'active' | 'done'
  metadata?: {
    permission_warning?: {
      runtime_confirmed: boolean
      source: 'openclaude_startup_alert'
    }
    duration_ms?: number
  }
}

/** Evento compactado do histórico de um turno (ver GET /conversations/:id/activity). */
export interface ConversationActivityEvent {
  type: string
  data: Record<string, unknown>
  at: string | null
}

/** Um turno do agente com os eventos que de facto aconteceram. */
export interface ConversationActivityTurn {
  task_id: string
  user_message_id: string | null
  status: string
  model_used: string | null
  created_at: string
  completed_at: string | null
  last_event_at: string | null
  events: ConversationActivityEvent[]
}

export interface ContextProgressEvent {
  label: string
  current_value: number | null
  limit_value: number | null
  percent: number | null
  financial: false
}

export type SubagentActivityState =
  | 'loading'
  | 'streaming'
  | 'tool-running'
  | 'permission-request'
  | 'permission-timeout'
  | 'stalled'
  | 'canceled'
  | 'failed'
  | 'done'

export interface SubagentActivityEvent {
  id: string
  name: string
  state: SubagentActivityState
  detail: string
}

export interface SubagentGroupEvent {
  parent_turn_id: string | null
  label: string
  collapsible: boolean
  activities: SubagentActivityEvent[]
}

export type RuntimeStateKind =
  | 'permission-timeout'
  | 'stalled'
  | 'canceled'
  | 'failed'
  | 'done'

export interface RuntimeStateEvent {
  state: RuntimeStateKind
  label: string
  detail: string
  terminal: boolean
}

export interface StreamHandlers {
  onText(accumulated: string): void
  onToolStart(tool: ToolStartEvent): void
  onToolResult(tool: ToolResultEvent): void
  onCommandStart? (event: CommandStartEvent): void
  onCommandResult? (event: CommandResultEvent): void
  onActionRequired(action: ActionRequiredEvent): void
  onStatus(status: StatusEvent): void
  onError(message: string): void
  onCursor? (cursor: number): void
  onPayloadDiagnostic? (diagnostics: PayloadSizeBreakdown): void
  onContextProgress? (progress: ContextProgressEvent): void
  onSubagentGroup? (group: SubagentGroupEvent): void
  onRuntimeState? (state: RuntimeStateEvent): void
  /** Acumulador final de tokens/modelo enviado quando o agente termina o turno. */
  onDone? (usage: DoneEvent): void
  signal?: AbortSignal
}
