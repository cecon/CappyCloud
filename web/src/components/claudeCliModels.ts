import type { AiModel, AgentRuntime, PlanUsage, PlanUsageWindow } from '../api'

/**
 * Modelos do Claude CLI: vêm da assinatura do `claude login` da sandbox, não do
 * catálogo. A API só aceita esses ids em sandbox com runtime Claude CLI.
 */
const FAMILIES = [
  { family: 'opus', label: 'Claude Opus' },
  { family: 'sonnet', label: 'Claude Sonnet' },
  { family: 'haiku', label: 'Claude Haiku' },
] as const

export const CLAUDE_CLI_DEFAULT_MODEL = 'claude-cli/sonnet'

export const CLAUDE_CLI_MODELS: AiModel[] = FAMILIES.map(({ family, label }) => ({
  id: `claude-cli/${family}`,
  provider_id: 'claude-cli',
  model_id: `claude-cli/${family}`,
  display_name: `${label} · Claude CLI`,
  capabilities: ['text', 'vision'],
  is_default: {},
  context_window: 200_000,
  input_cost_per_1m_usd: null,
  output_cost_per_1m_usd: null,
  tier: 'paid',
  active: true,
  created_at: '',
}))

export function isClaudeCliModel(modelId: string | null | undefined): boolean {
  return CLAUDE_CLI_MODELS.some((model) => model.model_id === modelId)
}

/**
 * Modelo do Claude CLI equivalente ao escolhido: o próprio, a mesma família
 * (ex.: "anthropic/claude-opus-4.7" → Opus) ou Sonnet — igual ao sandbox.
 */
export function claudeCliModelFor(modelId: string | null | undefined): string {
  if (isClaudeCliModel(modelId)) return modelId as string
  const name = (modelId ?? '').toLowerCase()
  const match = FAMILIES.find(({ family }) => name.includes(family))
  return match ? `claude-cli/${match.family}` : CLAUDE_CLI_DEFAULT_MODEL
}

export function usesClaudeCli(runtime: AgentRuntime | null | undefined): boolean {
  return runtime === 'claude_cli'
}

function resetText(window: PlanUsageWindow, withDate: boolean): string {
  if (!window.resets_at) return ''
  const when = new Date(window.resets_at)
  if (Number.isNaN(when.getTime())) return ''
  const time = when.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })
  const date = when.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' })
  return `, renova ${withDate ? `em ${date} às ` : 'às '}${time}`
}

/**
 * Selo da resposta no Claude CLI: quanto sobra da janela de 5h da assinatura
 * (no lugar do custo, que não existe por token). `null` sem dados de uso.
 */
export function planUsageBadge(plan: PlanUsage | null | undefined): { label: string; title: string; low: boolean } | null {
  const fiveHour = plan?.five_hour
  if (!fiveHour || fiveHour.used_pct == null) return null
  const free = Math.max(0, Math.round(100 - fiveHour.used_pct))
  const parts = [`Janela de 5h: ${Math.round(fiveHour.used_pct)}% usado${resetText(fiveHour, false)}.`]
  const week = plan?.seven_day
  if (week && week.used_pct != null) {
    parts.push(`Semana: ${Math.round(week.used_pct)}% usado${resetText(week, true)}.`)
  }
  return { label: `5h: ${free}% livre`, title: parts.join(' '), low: free <= 20 }
}
