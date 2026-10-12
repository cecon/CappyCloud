import { useState } from 'react'
import { Group, Text } from '@/components/ui/legacy'
import { IconCheck, IconChevronDown, IconChevronUp } from '@tabler/icons-react'
import type { ChatMessage } from '../../api'
import styles from '../MessageTimeline.module.css'

export interface SessionStageState {
  key: string
  label: string
  detail?: string
  status: 'pending' | 'active' | 'done'
}

export function MessageUsage({ message }: { message: ChatMessage }) {
  const { model_used, prompt_tokens = 0, completion_tokens = 0, cost_usd = 0 } = message
  if (!model_used) return null

  const modelShort = model_used.includes('/') ? model_used.split('/').slice(-1)[0] : model_used
  const totalTokens = prompt_tokens + completion_tokens

  let costLabel: string
  if (cost_usd > 0) {
    costLabel = cost_usd < 0.001
      ? `$${(cost_usd * 1000).toFixed(3)}m`
      : `$${cost_usd.toFixed(4)}`
  } else if (totalTokens === 0) {
    costLabel = 'Uso não informado'
  } else {
    costLabel = 'Free'
  }

  return (
    <div className={styles.messageUsage}>
      <span className={styles.messageUsageModel}>{modelShort}</span>
      <span className={styles.messageUsageSep}>·</span>
      {totalTokens > 0 && (
        <>
          <span className={styles.messageUsageTokens}>{totalTokens.toLocaleString()} tokens</span>
          <span className={styles.messageUsageSep}>·</span>
        </>
      )}
      <span className={cost_usd === 0 ? styles.messageUsageFree : styles.messageUsageCost}>{costLabel}</span>
    </div>
  )
}

export function SessionProgressInline({ stages }: { stages: SessionStageState[] }) {
  const [expanded, setExpanded] = useState(true)
  const allDone = stages.every((s) => s.status === 'done')

  return (
    <div className={styles.sessionProgress}>
      <button className={styles.sessionProgressToggle} onClick={() => setExpanded((v) => !v)}>
        <span className={styles.sessionProgressTitle}>
          {allDone ? 'Sessão pronta' : 'Iniciando sessão…'}
        </span>
        {expanded ? <IconChevronUp size={12} /> : <IconChevronDown size={12} />}
      </button>
      {expanded && (
        <div className={styles.sessionProgressList}>
          {stages.map((stage) => (
            <Group key={stage.key} gap={6} wrap="nowrap" align="flex-start">
              {stage.status === 'done' ? (
                <IconCheck size={12} color="var(--cc-success)" style={{ marginTop: 2, flexShrink: 0 }} />
              ) : (
                <div className={styles.pendingDot} />
              )}
              <div>
                <Text size="xs" c={stage.status === 'pending' ? 'dimmed' : undefined}>
                  {stage.label}
                </Text>
                {stage.detail && (
                  <Text size="xs" c="dimmed" style={{ opacity: 0.6 }}>
                    {stage.detail}
                  </Text>
                )}
              </div>
            </Group>
          ))}
        </div>
      )}
    </div>
  )
}
