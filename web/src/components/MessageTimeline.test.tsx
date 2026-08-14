import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { MessageTimeline } from './MessageTimeline'

const baseProps = {
  messages: [],
  pendingText: '',
  pendingTools: [],
  sessionProgress: [],
  pendingAction: null,
  showThinking: false,
  streaming: true,
  ratings: {},
  onRate: vi.fn(),
  onFork: vi.fn(),
  onActionReply: vi.fn(),
}

describe('MessageTimeline', () => {
  it('renders context progress as runtime activity rather than usage metadata', () => {
    render(
      <MessageTimeline
        {...baseProps}
        contextProgress={{
          label: 'Contexto usado',
          current_value: 50,
          limit_value: 200,
          percent: 25,
          financial: false,
        }}
      />,
    )

    expect(screen.getByText('Contexto usado')).toBeInTheDocument()
    expect(screen.getByText('25%')).toBeInTheDocument()
    expect(screen.queryByText(/Free/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/tokens/i)).not.toBeInTheDocument()
  })

  it('renders subagent groups and runtime notices in the streaming turn', () => {
    render(
      <MessageTimeline
        {...baseProps}
        subagentGroups={[
          {
            parent_turn_id: 'turn_1',
            label: 'Auxiliares',
            collapsible: true,
            activities: [{ id: 'agent_1', name: 'repo-a', state: 'done', detail: 'ok' }],
          },
        ]}
        runtimeStates={[
          {
            state: 'stalled',
            label: 'Execução sem novos eventos',
            detail: 'sem chunks novos',
            terminal: false,
          },
        ]}
      />,
    )

    expect(screen.getByText('Auxiliares')).toBeInTheDocument()
    expect(screen.getByText('1 atividades')).toBeInTheDocument()
    expect(screen.getByText('Execução sem novos eventos')).toBeInTheDocument()
    expect(screen.getByText('sem chunks novos')).toBeInTheDocument()
  })
})
