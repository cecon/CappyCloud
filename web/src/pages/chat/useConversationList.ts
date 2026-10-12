import { type UIEvent, useCallback, useMemo } from 'react'
import { CONVERSATION_PAGE_SIZE } from './constants'
import { groupConversations } from './formatting'
import type { ChatPageState } from './useChatPageState'

/** Busca, paginação incremental e agrupamento da lista lateral de conversas. */
export function useConversationList(st: ChatPageState) {
  const { conversationSearch, conversations, visibleConversationCount, setVisibleConversationCount } = st
  const normalizedConversationSearch = conversationSearch.trim().toLocaleLowerCase('pt-BR')
  const filteredConversations = useMemo(() => {
    // Arquivadas ficam no estado (a conversa aberta continua funcionando), mas
    // fora da lista: aparecem em "Arquivadas", no rodapé.
    const active = conversations.filter((conversation) => !conversation.archived_at)
    if (!normalizedConversationSearch) return active

    return active.filter((conversation) => {
      const repoText = conversation.repos
        ?.map((repo) => [repo.slug, repo.alias, repo.base_branch].filter(Boolean).join(' '))
        .join(' ') ?? ''
      const searchableText = `${conversation.title} ${repoText}`.toLocaleLowerCase('pt-BR')

      return searchableText.includes(normalizedConversationSearch)
    })
  }, [conversations, normalizedConversationSearch])
  const visibleConversations = useMemo(
    () => filteredConversations.slice(0, visibleConversationCount),
    [filteredConversations, visibleConversationCount],
  )
  const hiddenConversationCount = Math.max(
    filteredConversations.length - visibleConversations.length,
    0,
  )
  const sidebarConversationCountLabel = normalizedConversationSearch
    ? `${filteredConversations.length} de ${conversations.length} sessões`
    : hiddenConversationCount > 0
      ? `${visibleConversations.length} de ${conversations.length} sessões`
      : `${conversations.length} sessões`
  void sidebarConversationCountLabel
  const groups = groupConversations(visibleConversations)
  // setVisibleConversationCount é o setter estável do useState; listado só para o lint.
  const handleConversationListScroll = useCallback((event: UIEvent<HTMLDivElement>) => {
    if (hiddenConversationCount <= 0) return

    const list = event.currentTarget
    const distanceToBottom = list.scrollHeight - list.scrollTop - list.clientHeight
    if (distanceToBottom > 80) return

    setVisibleConversationCount((count) =>
      Math.min(count + CONVERSATION_PAGE_SIZE, filteredConversations.length),
    )
  }, [filteredConversations.length, hiddenConversationCount, setVisibleConversationCount])

  return { groups, hiddenConversationCount, handleConversationListScroll }
}
