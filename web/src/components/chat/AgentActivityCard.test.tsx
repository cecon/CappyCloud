import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { AgentActivityCard } from './AgentActivityCard'

describe('AgentActivityCard', () => {
  it('renders grouped subagent activity with normalized states', () => {
    render(
      <AgentActivityCard
        title="Auxiliares"
        status="running"
        detail="2 atividades auxiliares"
        activities={[
          { id: 'agent_1', name: 'repo-a', state: 'done', detail: 'ok' },
          { id: 'agent_2', name: 'repo-b', state: 'permission-timeout', detail: 'aguardando permissao' },
        ]}
      />,
    )

    expect(screen.getByText('Auxiliares')).toBeInTheDocument()
    expect(screen.getByText('2 atividades auxiliares')).toBeInTheDocument()
    expect(screen.getByText('repo-a')).toBeInTheDocument()
    expect(screen.getByText('repo-b')).toBeInTheDocument()
    expect(screen.getByText('Permissão expirada')).toBeInTheDocument()
  })

  it('surfaces stalled runtime state without marking it as a cost metric', () => {
    render(
      <AgentActivityCard
        title="Execução sem novos eventos"
        status="stalled"
        detail="sem chunks novos"
      />,
    )

    expect(screen.getByText('Execução sem novos eventos')).toBeInTheDocument()
    expect(screen.getByText('Sem novos eventos')).toBeInTheDocument()
    expect(screen.queryByText(/tokens/i)).not.toBeInTheDocument()
  })

  it('surfaces heavy iteration warnings', () => {
    render(
      <AgentActivityCard
        title="Iteracao pesada"
        status="warning"
        detail="45 ferramentas chamadas nesta rodada"
      />,
    )

    expect(screen.getByText('Iteracao pesada')).toBeInTheDocument()
    expect(screen.getByText('Atencao')).toBeInTheDocument()
    expect(screen.getByText('45 ferramentas chamadas nesta rodada')).toBeInTheDocument()
  })
})
