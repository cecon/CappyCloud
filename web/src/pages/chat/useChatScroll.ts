import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { ActiveChatProps } from './ActiveChat.types'
import { deriveChatNavigationMarkers, type ChatNavigationMarker } from '../../components/chat/chatNavigationMarkers'
import { STICKY_SCROLL_THRESHOLD_PX } from './constants'

type ChatScrollParams = Pick<
  ActiveChatProps,
  | 'messages' | 'thoughtSteps' | 'activityTraces' | 'pendingAction' | 'contextProgress'
  | 'subagentGroups' | 'runtimeStates' | 'streaming' | 'conversationId'
>

/** Auto-scroll "grudado" no fim, marcadores de navegação e botão de novas mensagens. */
export function useChatScroll({
  messages, thoughtSteps, activityTraces, pendingAction, contextProgress, subagentGroups,
  runtimeStates, streaming, conversationId,
}: ChatScrollParams) {
  const scrollRef = useRef<HTMLDivElement>(null)
  const messageTargetRefs = useRef<Record<string, HTMLDivElement | null>>({})
  const activeMarkerFrameRef = useRef<number | null>(null)
  const shouldStickToBottomRef = useRef(true)
  const [showJumpToLatest, setShowJumpToLatest] = useState(false)
  const [activeMarkerId, setActiveMarkerId] = useState<string | null>(null)

  /** Mantém o auto-scroll apenas quando o usuário já está no fim da conversa. */
  const updateStickyScroll = useCallback(() => {
    const viewport = scrollRef.current
    if (!viewport) return true
    const distanceFromBottom = viewport.scrollHeight - viewport.scrollTop - viewport.clientHeight
    const isNearBottom = distanceFromBottom <= STICKY_SCROLL_THRESHOLD_PX
    shouldStickToBottomRef.current = isNearBottom
    if (isNearBottom) setShowJumpToLatest(false)
    return isNearBottom
  }, [])

  const navigationMarkers = useMemo(() => deriveChatNavigationMarkers(messages), [messages])
  const resolvedActiveMarkerId = (
    activeMarkerId && navigationMarkers.some((marker) => marker.id === activeMarkerId)
      ? activeMarkerId
      : navigationMarkers[navigationMarkers.length - 1]?.id ?? null
  )

  const updateActiveMarker = useCallback(() => {
    if (activeMarkerFrameRef.current !== null) return
    activeMarkerFrameRef.current = requestAnimationFrame(() => {
      activeMarkerFrameRef.current = null
      const viewport = scrollRef.current
      if (!viewport || navigationMarkers.length === 0) {
        setActiveMarkerId(null)
        return
      }
      const viewportTop = viewport.getBoundingClientRect().top
      const anchorLine = viewportTop + Math.min(180, viewport.clientHeight * 0.32)
      let bestMarker = navigationMarkers[0]
      let bestDistance = Number.POSITIVE_INFINITY
      for (const marker of navigationMarkers) {
        const node = messageTargetRefs.current[marker.targetId]
        if (!node) continue
        const distance = Math.abs(node.getBoundingClientRect().top - anchorLine)
        if (distance < bestDistance) {
          bestDistance = distance
          bestMarker = marker
        }
      }
      setActiveMarkerId(bestMarker.id)
    })
  }, [navigationMarkers])

  const handleScrollPositionChange = useCallback(() => {
    updateStickyScroll()
    updateActiveMarker()
  }, [updateActiveMarker, updateStickyScroll])

  const setMessageTargetRef = useCallback((targetId: string) => (node: HTMLDivElement | null) => {
    if (node) {
      messageTargetRefs.current[targetId] = node
    } else {
      delete messageTargetRefs.current[targetId]
    }
  }, [])

  const activateNavigationMarker = useCallback((marker: ChatNavigationMarker) => {
    const node = messageTargetRefs.current[marker.targetId]
    if (!node) return
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    shouldStickToBottomRef.current = false
    setShowJumpToLatest(true)
    setActiveMarkerId(marker.id)
    node.scrollIntoView({ behavior: reduceMotion ? 'auto' : 'smooth', block: 'start' })
  }, [])

  /** Volta para as mensagens novas e reativa o acompanhamento do streaming. */
  const scrollToLatest = useCallback((behavior: ScrollBehavior = 'auto') => {
    const viewport = scrollRef.current
    if (!viewport) return
    shouldStickToBottomRef.current = true
    setShowJumpToLatest(false)
    viewport.scrollTo({ top: viewport.scrollHeight, behavior })
  }, [])

  useEffect(() => {
    shouldStickToBottomRef.current = true
    requestAnimationFrame(() => scrollToLatest())
  }, [conversationId, scrollToLatest])

  useEffect(() => () => {
    if (activeMarkerFrameRef.current !== null) cancelAnimationFrame(activeMarkerFrameRef.current)
  }, [])

  useEffect(() => {
    if (shouldStickToBottomRef.current) {
      requestAnimationFrame(() => scrollToLatest())
    } else {
      requestAnimationFrame(() => setShowJumpToLatest(true))
    }
  }, [messages, thoughtSteps, activityTraces, pendingAction, contextProgress, subagentGroups, runtimeStates, streaming, scrollToLatest])

  return {
    scrollRef,
    navigationMarkers,
    resolvedActiveMarkerId,
    activateNavigationMarker,
    handleScrollPositionChange,
    setMessageTargetRef,
    showJumpToLatest,
    scrollToLatest,
  }
}

export type ChatScroll = ReturnType<typeof useChatScroll>
