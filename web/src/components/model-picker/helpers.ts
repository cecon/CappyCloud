import type { AiModel } from '../../api'

export interface NormalizedRow {
  model: AiModel
  provider: string
  cleanName: string
  searchKey: string
}

export function normalize(models: AiModel[]): NormalizedRow[] {
  return models.map((m) => {
    const slashIdx = m.model_id.indexOf('/')
    const provider = slashIdx > 0 ? m.model_id.slice(0, slashIdx) : 'outro'
    const colonIdx = m.display_name.indexOf(':')
    const cleanName =
      colonIdx > 0 ? m.display_name.slice(colonIdx + 1).trim() : m.display_name
    return {
      model: m,
      provider,
      cleanName,
      searchKey: `${m.display_name} ${m.model_id} ${provider}`.toLowerCase(),
    }
  })
}

export function fmtCost(value: number | null | undefined): string {
  if (value == null) return '?? '
  if (value === 0) return 'free'
  if (value < 0.01) return `$${value.toFixed(4)}`
  return `$${value.toFixed(2)}`
}

export function fmtCtx(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${Math.round(n / 1_000)}k`
  return String(n)
}

export function modelStateLabel(model: AiModel): string | null {
  if (!model.active) return 'retirado'
  // Claude CLI: cobra da assinatura do `claude login`, não por token.
  if (model.provider_id === 'claude-cli') return 'assinatura'
  if (model.tier === 'paid') return 'pago'
  if (model.tier === 'unknown' || model.input_cost_per_1m_usd == null || model.output_cost_per_1m_usd == null) {
    return 'preço desconhecido'
  }
  return null
}
