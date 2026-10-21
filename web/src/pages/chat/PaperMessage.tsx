import { Text } from '@/components/ui/legacy'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { PayloadSizeBreakdown, PlanUsage } from '../../api'
import { planUsageBadge } from '../../components/claudeCliModels'
import styles from '../../components/chat.module.css'
import { AgentBubble } from './AgentBubble'
import { formatCostUsd, heavyUsageReason } from './formatting'
import { markdownComponents } from './markdownComponents'
import { PayloadDiagnosticSummary } from './PayloadDiagnosticSummary'

export function PaperMessage({
  role,
  content,
  streaming,
  modelUsed,
  promptTokens,
  completionTokens,
  costUsd,
  planUsage,
  payloadDiagnostics,
}: {
  role: string
  content: string
  streaming?: boolean
  modelUsed?: string | null
  promptTokens?: number
  completionTokens?: number
  costUsd?: number
  planUsage?: PlanUsage | null
  payloadDiagnostics?: PayloadSizeBreakdown | null
}) {
  const isUser = role === 'user'
  const totalTokens = (promptTokens ?? 0) + (completionTokens ?? 0)
  const hasUsage =
    !isUser && (totalTokens > 0 || !!modelUsed)
  // Claude CLI (tem planUsage): os tokens de entrada são quase todos cache barato;
  // só o custo equivalente indica uma resposta pesada.
  const usageWarning = isUser
    ? null
    : planUsage
      ? heavyUsageReason(0, 0, costUsd)
      : heavyUsageReason(promptTokens, completionTokens, costUsd)
  // Claude CLI: o custo é o equivalente pela tabela da API (coberto pela assinatura);
  // o uso das janelas de 5h/7d fica na dica, sem ocupar espaço.
  const planBadge = planUsageBadge(planUsage)
  const costLabel = totalTokens === 0 && (costUsd ?? 0) === 0
    ? 'uso não informado'
    : formatCostUsd(costUsd ?? 0)
  const costTitle = planBadge
    ? `Custo equivalente na API da Anthropic, coberto pela assinatura. ${planBadge.title}`
    : undefined
  const messageBubble = (
    <div className={`${styles.message} ${isUser ? styles.messageUser : styles.messageAgent}`}>
      <Text
        size="xs"
        mb={4}
        style={{
          color: isUser ? 'rgba(255,255,255,0.55)' : 'var(--cc-on-surface-variant)',
          fontFamily: 'Space Grotesk, sans-serif',
          fontWeight: 600,
          letterSpacing: '0.06em',
          textTransform: 'uppercase',
          fontSize: '0.6rem',
        }}
      >
        {isUser ? 'Tu' : 'Agente'}
      </Text>
      {isUser ? (
        <Text
          size="sm"
          style={{
            color: '#fff',
            fontFamily: 'Inter, sans-serif',
            lineHeight: 1.6,
            whiteSpace: 'pre-wrap',
          }}
        >
          {content}
        </Text>
      ) : (
        <div className={styles.markdownBody}>
          <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>{content}</ReactMarkdown>
          {streaming && <span className={styles.streamingCursor} aria-hidden />}
        </div>
      )}
      {!isUser && payloadDiagnostics && (
        <PayloadDiagnosticSummary diagnostics={payloadDiagnostics} />
      )}
      {usageWarning && (
        <div className={styles.heavyUsageNotice} role="note">
          <span className={styles.icon} aria-hidden="true">speed</span>
          <span>
            Iteração pesada: {usageWarning}.{' '}
            {planUsage
              ? 'Um modelo menor (Sonnet ou Haiku) gasta menos da janela da assinatura.'
              : 'Use Rápido quando quiser limitar a próxima rodada.'}
          </span>
        </div>
      )}
      {hasUsage && (
        <div className={styles.messageUsageFooter}>
          {modelUsed && <span className={styles.messageUsageModel}>{modelUsed}</span>}
          {totalTokens > 0 && (
            <span className={styles.messageUsageTokens}>
              {(promptTokens ?? 0).toLocaleString('pt-BR')} in · {(completionTokens ?? 0).toLocaleString('pt-BR')} out
            </span>
          )}
          <span
            className={styles.messageUsageCost}
            title={costTitle}
            style={planBadge?.low ? { color: 'var(--destructive)' } : undefined}
          >
            {costLabel}
          </span>
        </div>
      )}
    </div>
  )

  if (isUser) return messageBubble
  return <AgentBubble>{messageBubble}</AgentBubble>
}
