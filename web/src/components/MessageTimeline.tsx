import { useState } from 'react'
import { ActionIcon, Text, Timeline, Tooltip } from '@/components/ui/legacy'
import {
  IconThumbDown,
  IconThumbDownFilled,
  IconThumbUp,
  IconThumbUpFilled,
  IconGitFork,
  IconTerminal2,
  IconRobot,
  IconUser,
  IconCopy,
  IconCopyCheck,
} from '@tabler/icons-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { ThinkingIndicator } from './ThinkingIndicator'
import { ToolCallCard, type ToolCallState } from './ToolCallCard'
import { ActionRequiredCard } from './ActionRequiredCard'
import type {
  ActionRequiredEvent,
  ChatMessage,
  ContextProgressEvent,
  RuntimeStateEvent,
  SubagentGroupEvent,
} from '../api'
import styles from './MessageTimeline.module.css'
import { MessageUsage, SessionProgressInline, type SessionStageState } from './message-timeline/MessageExtras'

export type MessageRating = 'up' | 'down'

interface MessageTimelineProps {
  messages: ChatMessage[]
  pendingText: string
  pendingTools: ToolCallState[]
  sessionProgress: SessionStageState[]
  pendingAction: ActionRequiredEvent | null
  contextProgress?: ContextProgressEvent | null
  subagentGroups?: SubagentGroupEvent[]
  runtimeStates?: RuntimeStateEvent[]
  showThinking: boolean
  streaming: boolean
  ratings: Record<string, MessageRating>
  onRate: (messageId: string, rating: MessageRating) => void
  onFork: (messageId: string) => void
  onActionReply: (reply: string) => void
}

export function MessageTimeline({
  messages,
  pendingText,
  pendingTools,
  sessionProgress,
  pendingAction,
  contextProgress,
  subagentGroups = [],
  runtimeStates = [],
  showThinking,
  streaming,
  ratings,
  onRate,
  onFork,
  onActionReply,
}: MessageTimelineProps) {
  return (
    <Timeline
      bulletSize={28}
      lineWidth={1}
      classNames={{
        root: styles.timelineRoot,
        item: styles.timelineItem,
        itemBullet: styles.bullet,
        itemBody: styles.itemBody,
      }}
    >
      {messages.map((msg) => (
        <MessageItem
          key={msg.id}
          message={msg}
          rating={ratings[msg.id]}
          onRate={(r) => onRate(msg.id, r)}
          onFork={() => onFork(msg.id)}
          streaming={false}
        />
      ))}

      {/* Pending streaming response */}
      {streaming && (
        <Timeline.Item
          bullet={<IconRobot size={14} />}
          classNames={{ itemBullet: `${styles.bullet} ${styles.bulletAgent}` }}
        >
          {pendingTools.length > 0 && (
            <div className={styles.toolList}>
              {pendingTools.map((tool) => (
                <ToolCallCard key={tool.id} tool={tool} />
              ))}
            </div>
          )}
          {sessionProgress.length > 0 && (
            <SessionProgressInline stages={sessionProgress} />
          )}
          {(contextProgress || subagentGroups.length > 0 || runtimeStates.length > 0) && (
            <div className={styles.activityList}>
              {contextProgress && (
                <div className={styles.activityNotice}>
                  <strong>{contextProgress.label}</strong>
                  {contextProgress.percent != null && <span>{contextProgress.percent}%</span>}
                </div>
              )}
              {subagentGroups.map((group) => (
                <div key={group.parent_turn_id ?? group.label} className={styles.activityNotice}>
                  <strong>{group.label}</strong>
                  <span>{group.activities.length} atividades</span>
                </div>
              ))}
              {runtimeStates.map((state, index) => (
                <div key={`${state.state}-${index}`} className={styles.activityNotice}>
                  <strong>{state.label}</strong>
                  {state.detail && <span>{state.detail}</span>}
                </div>
              ))}
            </div>
          )}
          {showThinking && (
            <ThinkingIndicator />
          )}
          {pendingText && (
            <div className={styles.agentContent}>
              <div className={styles.markdownBody}>
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{pendingText}</ReactMarkdown>
                <span className={styles.streamingCursor} aria-hidden />
              </div>
            </div>
          )}
        </Timeline.Item>
      )}

      {/* Action required card */}
      {pendingAction && (
        <Timeline.Item
          bullet={<IconTerminal2 size={14} />}
          classNames={{ itemBullet: `${styles.bullet} ${styles.bulletWarning}` }}
        >
          <ActionRequiredCard action={pendingAction} onReply={(reply) => onActionReply(reply)} />
        </Timeline.Item>
      )}
    </Timeline>
  )
}

function MessageItem({
  message,
  rating,
  onRate,
  onFork,
}: {
  message: ChatMessage
  rating?: MessageRating
  onRate: (r: MessageRating) => void
  onFork: () => void
  streaming?: boolean
}) {
  const isUser = message.role === 'user'
  const [hovered, setHovered] = useState(false)
  const [copied, setCopied] = useState(false)

  function handleCopy() {
    navigator.clipboard.writeText(message.content).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  return (
    <Timeline.Item
      bullet={isUser ? <IconUser size={13} /> : <IconRobot size={13} />}
      classNames={{
        itemBullet: `${styles.bullet} ${isUser ? styles.bulletUser : styles.bulletAgent}`,
      }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      <div className={styles.messageWrapper}>
        <div className={`${styles.messageMeta}`}>
          <span className={styles.messageRole}>{isUser ? 'Você' : 'Agente'}</span>
          <span className={styles.messageTime}>
            {new Date(message.created_at).toLocaleTimeString('pt-PT', {
              hour: '2-digit',
              minute: '2-digit',
            })}
          </span>

          {/* Actions — visible on hover */}
          {!isUser && (
            <div className={`${styles.messageActions} ${hovered ? styles.messageActionsVisible : ''}`}>
              <Tooltip label="Gostei" withArrow>
                <ActionIcon
                  variant="subtle"
                  size="xs"
                  color={rating === 'up' ? 'green' : 'gray'}
                  onClick={() => onRate(rating === 'up' ? 'up' : 'up')}
                >
                  {rating === 'up' ? <IconThumbUpFilled size={12} /> : <IconThumbUp size={12} />}
                </ActionIcon>
              </Tooltip>
              <Tooltip label="Não gostei" withArrow>
                <ActionIcon
                  variant="subtle"
                  size="xs"
                  color={rating === 'down' ? 'red' : 'gray'}
                  onClick={() => onRate('down')}
                >
                  {rating === 'down' ? <IconThumbDownFilled size={12} /> : <IconThumbDown size={12} />}
                </ActionIcon>
              </Tooltip>
              <Tooltip label="Fork a partir daqui" withArrow>
                <ActionIcon variant="subtle" size="xs" color="blue" onClick={onFork}>
                  <IconGitFork size={12} />
                </ActionIcon>
              </Tooltip>
              <Tooltip label={copied ? 'Copiado!' : 'Copiar resposta'} withArrow>
                <ActionIcon variant="subtle" size="xs" color={copied ? 'green' : 'gray'} onClick={handleCopy}>
                  {copied ? <IconCopyCheck size={12} /> : <IconCopy size={12} />}
                </ActionIcon>
              </Tooltip>
            </div>
          )}
        </div>

        {isUser ? (
          <div className={styles.userBubble}>
            <Text size="sm" style={{ whiteSpace: 'pre-wrap', lineHeight: 1.6 }}>
              {message.content}
            </Text>
          </div>
        ) : (
          <div className={styles.agentContent}>
            <div className={styles.markdownBody}>
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
            </div>
            <MessageUsage message={message} />
          </div>
        )}
      </div>
    </Timeline.Item>
  )
}
