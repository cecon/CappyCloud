import type { AiModel, AgentRuntime } from '../api'

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
