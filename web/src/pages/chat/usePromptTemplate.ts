import { useEffect, useRef } from 'react'
import type { ChatPageState } from './useChatPageState'

/** Prompt modelo do workspace da conversa nova ('' quando não há). */
export function promptTemplateFor(st: Pick<ChatPageState, 'activeId' | 'projectWorkspaces' | 'selectedWorkspaceId'>): string {
  if (st.activeId) return ''
  return st.projectWorkspaces.find((workspace) => workspace.id === st.selectedWorkspaceId)?.prompt_template ?? ''
}

/**
 * Conversa nova abre com o prompt modelo do workspace na caixa de mensagem.
 *
 * Só preenche quando a caixa está vazia ou ainda tem o modelo anterior (troca de
 * workspace): o que a pessoa já digitou nunca é apagado. Se ela apagar o modelo,
 * a caixa fica vazia até trocar de workspace ou abrir outra conversa nova.
 */
export function usePromptTemplate(st: ChatPageState): void {
  const { activeId, input, setInput } = st
  const template = promptTemplateFor(st)
  const applied = useRef('')
  const inputRef = useRef(input)
  useEffect(() => {
    inputRef.current = input
  }, [input])

  useEffect(() => {
    if (activeId) {
      // Abriu uma conversa (inclusive a restaurada ao carregar a página): o modelo
      // intocado sai da caixa; o que a pessoa digitou fica.
      if (applied.current && inputRef.current === applied.current) setInput('')
      applied.current = ''
      return
    }
    const current = inputRef.current
    if (current !== '' && current !== applied.current) return
    if (current !== template) setInput(template)
    applied.current = template
  }, [activeId, template, setInput])
}
