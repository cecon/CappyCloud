import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import type { AiModel } from '../api'
import { modelIdForAttachments, modelSwitchNotice } from '../pages/chat/attachments'
import { AttachmentTray } from './AttachmentTray'

function model(modelId: string, displayName: string, capabilities: string[]): AiModel {
  return {
    id: modelId,
    provider_id: 'provider-1',
    model_id: modelId,
    display_name: displayName,
    capabilities,
    is_default: {},
    context_window: 200000,
    input_cost_per_1m_usd: null,
    output_cost_per_1m_usd: null,
    tier: 'unknown',
    active: true,
    created_at: '2026-10-26T00:00:00Z',
  }
}

const MODELS = [
  model('claude-opus-5-5', 'Claude Opus 5.5 (Azure)', ['text']),
  model('gpt-6.1-sol', 'Azure GPT 6.1 Sol', ['text', 'vision']),
]

describe('troca de modelo por imagem', () => {
  it('troca para um modelo com visão e explica a troca', () => {
    const next = modelIdForAttachments(MODELS, 'claude-opus-5-5', true)

    expect(next).toBe('gpt-6.1-sol')
    expect(modelSwitchNotice(MODELS, 'claude-opus-5-5', next)).toBe(
      'Claude Opus 5.5 (Azure) não lê imagem; a mensagem vai com Azure GPT 6.1 Sol.',
    )
  })

  it('mantém o modelo quando ele já lê imagem', () => {
    const withVision = [model('claude-opus-5-5', 'Claude', ['text', 'vision']), ...MODELS.slice(1)]

    expect(modelIdForAttachments(withVision, 'claude-opus-5-5', true)).toBe('claude-opus-5-5')
  })

  it('mostra o aviso mesmo sem anexos e fecha pelo botão', () => {
    const onDismiss = vi.fn()
    render(
      <AttachmentTray
        items={[]}
        token="token"
        conversationId={null}
        onRemove={vi.fn()}
        notice={{ text: 'Claude não lê imagem; a mensagem vai com GPT.', onDismiss }}
      />,
    )

    expect(screen.getByRole('status')).toHaveTextContent('Claude não lê imagem')
    fireEvent.click(screen.getByRole('button', { name: 'Fechar aviso' }))
    expect(onDismiss).toHaveBeenCalled()
  })
})
