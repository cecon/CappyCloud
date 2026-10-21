import { Fragment } from 'react'
import { ScrollArea, Stack, Text } from '@/components/ui/legacy'
import type { ChatMessage } from '../../api'
import { ActionRequiredCard } from '../../components/ActionRequiredCard'
import { ChatVerticalNavigation } from '../../components/chat/ChatVerticalNavigation'
import { ThinkingIndicator } from '../../components/ThinkingIndicator'
import { ThinkingStream } from '../../components/ThinkingStream'
import styles from '../../components/chat.module.css'
import type { ActiveChatProps } from './ActiveChat.types'
import { AgentBubble } from './AgentBubble'
import { heavyToolReason } from './formatting'
import { PaperMessage } from './PaperMessage'
import { StreamActivityBubble } from './StreamActivityBubble'
import type { ActivityTrace } from './types'
import type { ChatScroll } from './useChatScroll'

type ChatMessageListProps = Pick<
  ActiveChatProps,
  | 'messages' | 'messagesLoading' | 'messagesError' | 'sessionProgressAnchor' | 'thoughtSteps'
  | 'activityTraces' | 'streamElapsedMs' | 'streamNowMs' | 'streamIdleMs' | 'pendingAction'
  | 'contextProgress' | 'subagentGroups' | 'runtimeStates' | 'streamToolStats' | 'showThinking'
  | 'streaming' | 'onActionReply'
> & { scroll: ChatScroll }

/** Coluna de mensagens: navegação, histórico, progresso do turno e ação pendente. */
export function ChatMessageList({
  messages, messagesLoading, messagesError, sessionProgressAnchor, thoughtSteps, activityTraces,
  streamElapsedMs, streamNowMs, streamIdleMs, pendingAction, contextProgress, subagentGroups,
  runtimeStates, streamToolStats, showThinking, streaming, onActionReply, scroll,
}: ChatMessageListProps) {
  const {
    scrollRef, navigationMarkers, resolvedActiveMarkerId, activateNavigationMarker,
    handleScrollPositionChange, setMessageTargetRef, showJumpToLatest, scrollToLatest,
  } = scroll
  const lastUserMessageId = [...messages].reverse().find((message) => message.role === 'user')?.id
  /**
   * O turno ao vivo fica guardado sob o id local da mensagem; quando as
   * mensagens voltam do servidor com outro id, a última mensagem do utilizador
   * continua ligada ao rastro ao vivo até o histórico ser recarregado.
   */
  const isLiveTurnMessage = (message: ChatMessage): boolean =>
    !!sessionProgressAnchor &&
    (message.id === sessionProgressAnchor.id ||
      (message.id === lastUserMessageId && message.content === sessionProgressAnchor.content))
  const activityTraceFor = (message: ChatMessage): ActivityTrace | null => {
    if (message.role !== 'user') return null
    if (activityTraces[message.id]) return activityTraces[message.id]
    if (isLiveTurnMessage(message) && sessionProgressAnchor) {
      return activityTraces[sessionProgressAnchor.id] ?? null
    }
    return null
  }
  const heavyStreamingReason = heavyToolReason(streamToolStats)

  return (
      <div className={styles.chatBody}>
        {/* Messages column */}
        <div className={styles.chatMessages}>
          <ChatVerticalNavigation
            markers={navigationMarkers}
            activeMarkerId={resolvedActiveMarkerId}
            onMarkerActivate={activateNavigationMarker}
          />
          <ScrollArea
            className={styles.messageArea}
            viewportRef={scrollRef}
            type="auto"
            onScrollPositionChange={handleScrollPositionChange}
          >
            <div className={styles.chatScrollInner}>
              <div className={styles.chatThread}>
              <Stack gap="sm" p="md">
              {messagesLoading && (
                <div className={styles.chatStateCard}>
                  <ThinkingIndicator label="A carregar conversa…" />
                </div>
              )}
              {messagesError && (
                <div className={`${styles.chatStateCard} ${styles.chatStateCardError}`} role="alert">
                  <Text size="sm" fw={600}>Não foi possível carregar esta conversa.</Text>
                  <Text size="xs" c="dimmed">{messagesError}</Text>
                </div>
              )}
              {!messagesLoading && !messagesError && messages.length === 0 && !streaming && (
                <div className={styles.chatStateCard}>
                  <Text size="sm" c="dimmed">Esta conversa ainda não tem mensagens.</Text>
                </div>
              )}
              {messages.map((m) => {
                const trace = activityTraceFor(m)
                const liveTurn = streaming && isLiveTurnMessage(m)
                return (
                <Fragment key={m.id}>
                  <div
                    ref={setMessageTargetRef(`message-${m.id}`)}
                    className={styles.messageAnchor}
                    data-chat-marker-target={`message-${m.id}`}
                  >
                    <PaperMessage
                      key={m.id}
                      role={m.role}
                      content={m.content}
                      modelUsed={m.model_used ?? null}
                      promptTokens={m.prompt_tokens ?? 0}
                      completionTokens={m.completion_tokens ?? 0}
                      costUsd={m.cost_usd ?? 0}
                      planUsage={m.plan_usage ?? null}
                      payloadDiagnostics={m.payload_diagnostics ?? null}
                    />
                  </div>
                  {trace?.steps.length ? (
                    <AgentBubble compact>
                      <ThinkingStream
                        steps={trace.steps}
                        streaming={liveTurn}
                        elapsedMs={liveTurn ? streamElapsedMs : trace.elapsedMs}
                        idleMs={liveTurn ? streamIdleMs : 0}
                        interrupted={!!trace.interrupted}
                      />
                    </AgentBubble>
                  ) : null}
                </Fragment>
                )
              })}
              <StreamActivityBubble
                streaming={streaming}
                contextProgress={contextProgress}
                subagentGroups={subagentGroups}
                runtimeStates={runtimeStates}
                heavyStreamingReason={heavyStreamingReason}
                streamNowMs={streamNowMs}
              />
              {((thoughtSteps.length > 0 && !sessionProgressAnchor) || (streaming && showThinking)) && (
                <AgentBubble compact>
                  <Stack gap="xs">
                    {thoughtSteps.length > 0 && !sessionProgressAnchor && (
                      <ThinkingStream
                        steps={thoughtSteps}
                        streaming={streaming}
                        elapsedMs={streamElapsedMs}
                        idleMs={streamIdleMs}
                      />
                    )}
                    {streaming && showThinking && <ThinkingIndicator />}
                  </Stack>
                </AgentBubble>
              )}

              {pendingAction && (
                <AgentBubble compact>
                  <ActionRequiredCard action={pendingAction} onReply={onActionReply} />
                </AgentBubble>
              )}
              </Stack>
              </div>
            </div>
          </ScrollArea>
          {showJumpToLatest && (
            <button type="button" className={styles.jumpToLatestBtn} onClick={() => scrollToLatest('smooth')}>
              <span>Novas mensagens</span>
              <span className={styles.icon}>south</span>
            </button>
          )}
        </div>

      </div>
  )
}
