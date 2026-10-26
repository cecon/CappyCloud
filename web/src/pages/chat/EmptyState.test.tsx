import { createRef } from 'react'
import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { AiModel } from '../../api'
import { EmptyState } from './EmptyState'

const MODEL: AiModel = {
  id: 'model-1',
  provider_id: 'provider-1',
  model_id: 'claude-opus-5-5',
  display_name: 'Claude Opus 5.5 (Azure)',
  capabilities: ['text'],
  is_default: {},
  context_window: 200000,
  input_cost_per_1m_usd: null,
  output_cost_per_1m_usd: null,
  tier: 'unknown',
  active: true,
  created_at: '2026-10-26T00:00:00Z',
}

function renderEmptyState(setSelectedModelId = vi.fn()) {
  render(
    <EmptyState
      input=""
      setInput={vi.fn()}
      inputRef={createRef()}
      onExecute={vi.fn()}
      streaming={false}
      selectableWorkspaces={[]}
      projectWorkspaces={[]}
      selectedWorkspaceId=""
      setSelectedWorkspaceId={vi.fn()}
      newChatError={null}
      selectedSlug=""
      requireTicket={false}
      ticketNumber=""
      setTicketNumber={vi.fn()}
      ticketRef={createRef()}
      models={[MODEL]}
      selectedModelId=""
      setSelectedModelId={setSelectedModelId}
      permissionMode="bypass_permissions"
      setPermissionMode={vi.fn()}
      planModeEnabled={false}
      executionProfile="medium"
      setExecutionProfile={vi.fn()}
      permissionWarningRuntimeConfirmed={false}
      token="token"
      trayItems={[]}
      onPickFiles={vi.fn()}
      onPasteFiles={vi.fn()}
      onRemoveTrayItem={vi.fn()}
      trayNotice={null}
      fileInputRef={createRef()}
      isDragOver={false}
      setDragOver={vi.fn()}
    />,
  )
  return setSelectedModelId
}

describe('EmptyState', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('lets the user choose the model before the first message', () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('{"cards":[]}')))
    const setSelectedModelId = renderEmptyState()

    fireEvent.click(screen.getByRole('button', { name: /Modelo IA/i }))
    fireEvent.click(screen.getByText('Claude Opus 5.5 (Azure)'))

    expect(setSelectedModelId).toHaveBeenCalled()
  })
})
