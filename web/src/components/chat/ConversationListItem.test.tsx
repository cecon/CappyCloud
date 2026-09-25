import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import type { Conversation } from '../../api'
import { ConversationListItem } from './ConversationListItem'

const conversation: Conversation = {
  id: 'c1',
  title: 'Ao realizar a transmissão de um RPS',
  created_at: '2026-09-25T10:00:00Z',
  updated_at: '2026-09-25T10:00:00Z',
  sandbox_id: null,
  repos: [],
  session_root: null,
  permission_mode: 'bypass_permissions',
}

function setup(onRename = vi.fn().mockResolvedValue(undefined)) {
  const onArchive = vi.fn().mockResolvedValue(undefined)
  render(
    <ConversationListItem
      conversation={conversation}
      active={false}
      onSelect={vi.fn()}
      onRename={onRename}
      onArchive={onArchive}
    />,
  )
  return { onRename, onArchive, user: userEvent.setup() }
}

describe('ConversationListItem', () => {
  it('renomeia com duplo clique e Enter, uma vez só', async () => {
    const { onRename, user } = setup()
    await user.dblClick(screen.getByTitle(conversation.title))
    const input = screen.getByLabelText('Novo nome da conversa')
    await user.clear(input)
    await user.type(input, 'NFS-e SP cIndOp{Enter}')

    await waitFor(() => expect(onRename).toHaveBeenCalledTimes(1))
    expect(onRename).toHaveBeenCalledWith('NFS-e SP cIndOp')
  })

  it('Esc cancela sem salvar', async () => {
    const { onRename, user } = setup()
    await user.dblClick(screen.getByTitle(conversation.title))
    await user.type(screen.getByLabelText('Novo nome da conversa'), ' editado{Escape}')

    expect(onRename).not.toHaveBeenCalled()
    expect(screen.getByTitle(conversation.title)).toBeTruthy()
  })

  it('mostra o erro quando o servidor recusa', async () => {
    const { user } = setup(vi.fn().mockRejectedValue(new Error('O título não pode ficar vazio.')))
    await user.dblClick(screen.getByTitle(conversation.title))
    const input = screen.getByLabelText('Novo nome da conversa')
    await user.clear(input)
    await user.type(input, 'x{Enter}')

    expect(await screen.findByText('O título não pode ficar vazio.')).toBeTruthy()
  })
})
