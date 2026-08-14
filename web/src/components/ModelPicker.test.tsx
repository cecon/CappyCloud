import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import type { AiModel } from '../api'
import { ModelPicker } from './ModelPicker'

function model(overrides: Partial<AiModel> = {}): AiModel {
  return {
    id: overrides.id ?? 'model-1',
    provider_id: overrides.provider_id ?? 'provider-1',
    model_id: overrides.model_id ?? 'openrouter/free',
    display_name: overrides.display_name ?? 'OpenRouter: Free',
    capabilities: overrides.capabilities ?? ['text'],
    is_default: overrides.is_default ?? {},
    context_window: overrides.context_window ?? 128000,
    input_cost_per_1m_usd: 'input_cost_per_1m_usd' in overrides ? overrides.input_cost_per_1m_usd! : 0,
    output_cost_per_1m_usd: 'output_cost_per_1m_usd' in overrides ? overrides.output_cost_per_1m_usd! : 0,
    tier: overrides.tier ?? 'free',
    active: overrides.active ?? true,
    created_at: overrides.created_at ?? '2026-08-08T00:00:00Z',
  }
}

describe('ModelPicker', () => {
  it('shows a no-authorized-model state when the catalog is empty', () => {
    render(<ModelPicker models={[]} value="" onChange={vi.fn()} />)

    fireEvent.click(screen.getByRole('button', { name: /Modelo IA/i }))

    expect(screen.getByText('Nenhum modelo autorizado para este usuário.')).toBeInTheDocument()
  })

  it('marks unavailable selected models in the trigger', () => {
    render(<ModelPicker models={[]} value="openrouter/retired" onChange={vi.fn()} />)

    expect(screen.getByText('Modelo indisponível')).toBeInTheDocument()
  })

  it('labels paid, retired, and unknown-pricing rows without exposing auth state', () => {
    render(
      <ModelPicker
        value=""
        onChange={vi.fn()}
        models={[
          model({ id: 'paid', model_id: 'openai/paid', display_name: 'OpenAI Paid', tier: 'paid' }),
          model({ id: 'retired', model_id: 'openai/old', display_name: 'OpenAI Old', active: false }),
          model({
            id: 'unknown',
            model_id: 'openai/unknown',
            display_name: 'OpenAI Unknown',
            tier: 'unknown',
            input_cost_per_1m_usd: null,
            output_cost_per_1m_usd: null,
          }),
        ]}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: /Modelo IA/i }))

    expect(screen.getByText('pago')).toBeInTheDocument()
    expect(screen.getByText('retirado')).toBeInTheDocument()
    expect(screen.getByText('preço desconhecido')).toBeInTheDocument()
    expect(screen.queryByText(/Chave pendente/i)).not.toBeInTheDocument()
  })
})
