import type { ModelTier } from '../../api'

export type TierFilter = 'all' | ModelTier

export const TIER_OPTIONS: { value: TierFilter; label: string }[] = [
  { value: 'all', label: 'Todos' },
  { value: 'free', label: 'Free' },
  { value: 'paid', label: 'Paid' },
  { value: 'unknown', label: 'Sem preço' },
]

export function tierColor(t: ModelTier): string {
  if (t === 'free') return 'green'
  if (t === 'paid') return 'grape'
  return 'gray'
}

export function formatPrice(value: number | null): string {
  if (value === null) return '—'
  return `$${value.toFixed(2)}`
}

export function capabilityColor(capability: string): string {
  if (capability === 'embedding') return 'cyan'
  if (capability === 'vision') return 'grape'
  if (capability === 'text') return 'blue'
  return 'gray'
}
