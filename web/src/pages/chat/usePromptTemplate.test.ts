import { act, renderHook } from '@testing-library/react'
import { useState } from 'react'
import { describe, expect, it } from 'vitest'
import type { AccessibleWorkspace } from '../../api'
import type { ChatPageState } from './useChatPageState'
import { usePromptTemplate } from './usePromptTemplate'

const ws = (id: string, prompt_template = ''): AccessibleWorkspace => ({
  id, slug: id, name: id, sandbox_id: 'sb', ready: true, prompt_template, repositories: [],
})
const WORKSPACES = [ws('a', 'Chamado:\nMunicípio:'), ws('b', 'Modelo B'), ws('c')]

function useHarness(initial: { activeId?: string | null; workspaceId: string; input?: string }) {
  const [activeId, setActiveId] = useState<string | null>(initial.activeId ?? null)
  const [selectedWorkspaceId, setSelectedWorkspaceId] = useState(initial.workspaceId)
  const [input, setInput] = useState(initial.input ?? '')
  const st = { activeId, projectWorkspaces: WORKSPACES, selectedWorkspaceId, input, setInput } as unknown as ChatPageState
  usePromptTemplate(st)
  return { input, setInput, setActiveId, setSelectedWorkspaceId }
}

describe('usePromptTemplate', () => {
  it('conversa nova abre com o modelo e troca junto com o workspace', () => {
    const { result } = renderHook(() => useHarness({ workspaceId: 'a' }))
    expect(result.current.input).toBe('Chamado:\nMunicípio:')

    act(() => result.current.setSelectedWorkspaceId('b'))
    expect(result.current.input).toBe('Modelo B')

    act(() => result.current.setSelectedWorkspaceId('c'))
    expect(result.current.input).toBe('')
  })

  it('nunca apaga o que a pessoa já digitou', () => {
    const { result } = renderHook(() => useHarness({ workspaceId: 'a' }))
    act(() => result.current.setInput('Chamado: 123'))
    act(() => result.current.setSelectedWorkspaceId('b'))
    expect(result.current.input).toBe('Chamado: 123')
  })

  it('conversa aberta não recebe o modelo', () => {
    const { result } = renderHook(() => useHarness({ workspaceId: 'a', activeId: 'conv-1' }))
    expect(result.current.input).toBe('')

    act(() => result.current.setActiveId(null))
    expect(result.current.input).toBe('Chamado:\nMunicípio:')
  })

  it('conversa restaurada depois do carregamento tira o modelo intocado', () => {
    const { result } = renderHook(() => useHarness({ workspaceId: 'a' }))
    expect(result.current.input).toBe('Chamado:\nMunicípio:')

    act(() => result.current.setActiveId('conv-1'))
    expect(result.current.input).toBe('')
  })

  it('abrir conversa mantém o que a pessoa já editou', () => {
    const { result } = renderHook(() => useHarness({ workspaceId: 'a' }))
    act(() => result.current.setInput('Chamado: 99'))
    act(() => result.current.setActiveId('conv-1'))
    expect(result.current.input).toBe('Chamado: 99')
  })
})
