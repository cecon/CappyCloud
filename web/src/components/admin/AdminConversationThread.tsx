import { useEffect, useMemo, useState } from 'react'
import { Stack } from '@/components/ui/legacy'
import {
  type AdminConversationAttachment,
  type AdminConversationDetail,
  type ConversationActivityTurn,
  fetchAdminConversationActivity,
  fetchAdminConversationAttachments,
} from '../../api'
import { AgentBubble } from '../../pages/chat/AgentBubble'
import { PaperMessage } from '../../pages/chat/PaperMessage'
import { ThinkingStream } from '../ThinkingStream'
import { MessageAttachments } from '../chat/MessageAttachments'
import { buildHistoryTraces } from '../chat/thoughtSteps'
import { groupByMessage } from './attachmentsByMessage'
import styles from '../chat.module.css'

type Extras = { turns: ConversationActivityTurn[]; attachments: AdminConversationAttachment[] }

/**
 * A conversa como o usuário viu no chat: mesmos balões, os passos do agente
 * sob cada pergunta e os anexos enviados. Só leitura.
 */
export function AdminConversationThread({ detail, token }: { detail: AdminConversationDetail; token: string }) {
  const [extras, setExtras] = useState<Extras>({ turns: [], attachments: [] })
  const [warning, setWarning] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    // Passos e anexos são complemento: se falharem, as mensagens continuam visíveis.
    void Promise.allSettled([
      fetchAdminConversationActivity(token, detail.id),
      fetchAdminConversationAttachments(token, detail.id),
    ]).then(([turns, attachments]) => {
      if (cancelled) return
      setExtras({
        turns: turns.status === 'fulfilled' ? turns.value : [],
        attachments: attachments.status === 'fulfilled' ? attachments.value : [],
      })
      const failed = [turns, attachments].filter((r) => r.status === 'rejected').length
      setWarning(failed ? 'Não foi possível carregar os passos ou os anexos desta conversa.' : null)
    })
    return () => {
      cancelled = true
    }
  }, [token, detail.id])

  const traces = useMemo(() => buildHistoryTraces(extras.turns, detail.messages), [extras.turns, detail.messages])
  const attachmentsByMessage = useMemo(() => groupByMessage(extras.attachments), [extras.attachments])

  if (detail.messages.length === 0) {
    return <p className="text-sm text-muted-foreground">Sem mensagens.</p>
  }

  return (
    <div className={styles.chatThread}>
      {warning && <p className="mb-2 text-xs text-destructive">{warning}</p>}
      <Stack gap="sm">
        {detail.messages.map((message) => {
          const trace = message.role === 'user' ? traces[message.id] : undefined
          const files = attachmentsByMessage.get(message.id) ?? []
          return (
            <div key={message.id} className="flex flex-col gap-2">
              {message.role === 'user' && (
                <span className="self-end text-[0.65rem] text-muted-foreground">
                  {formatDateTime(message.created_at)}
                </span>
              )}
              <PaperMessage
                role={message.role}
                content={message.content}
                authorLabel={detail.user_email ?? 'Usuário'}
                modelUsed={message.model_used}
                promptTokens={message.prompt_tokens}
                completionTokens={message.completion_tokens}
                costUsd={message.cost_usd}
                planUsage={message.plan_usage ?? null}
                payloadDiagnostics={message.payload_diagnostics ?? null}
                attachments={
                  files.length > 0 ? (
                    <MessageAttachments
                      attachments={files}
                      token={token}
                      conversationId={detail.id}
                      source="admin"
                    />
                  ) : undefined
                }
              />
              {trace?.steps.length ? (
                <AgentBubble compact>
                  <ThinkingStream
                    steps={trace.steps}
                    streaming={false}
                    elapsedMs={trace.elapsedMs}
                    interrupted={!!trace.interrupted}
                  />
                </AgentBubble>
              ) : null}
            </div>
          )
        })}
      </Stack>
    </div>
  )
}

function formatDateTime(value: string): string {
  return new Date(value).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' })
}
