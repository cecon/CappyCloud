import type { ConversationUsage, DoneEvent } from '../../api'
import styles from '../../components/chat.module.css'
import { fallbackReasonLabel, formatCostUsd } from './formatting'

/** Pílulas de uso (tokens, custo e fallback de modelo) da barra de contexto. */
export function UsagePills({ convUsage, liveUsage }: {
  convUsage: ConversationUsage
  liveUsage: DoneEvent | null
}) {
  const hasUsageMeta =
    convUsage.total_prompt_tokens > 0 ||
    convUsage.total_completion_tokens > 0 ||
    (liveUsage ? liveUsage.prompt_tokens > 0 || liveUsage.completion_tokens > 0 : false) ||
    !!liveUsage?.fallback
  if (!hasUsageMeta) return null
  return (
              <>
              {(convUsage.total_prompt_tokens > 0 || convUsage.total_completion_tokens > 0) && (
                <div
                  className={styles.chatContextPill}
                  title={`Total da conversa: ${convUsage.total_prompt_tokens} in + ${convUsage.total_completion_tokens} out`}
                >
                  <span className={`${styles.icon} ${styles.chatContextIcon}`}>insights</span>
                  <span className={styles.chatContextText}>
                    {(convUsage.total_prompt_tokens + convUsage.total_completion_tokens).toLocaleString('pt-BR')} tok
                    · {formatCostUsd(convUsage.total_cost_usd)}
                  </span>
                </div>
              )}
              {liveUsage && (liveUsage.prompt_tokens > 0 || liveUsage.completion_tokens > 0) && (
                <div
                  className={styles.chatContextPill}
                  title="Último turno (ainda não consolidado nos totais)"
                >
                  <span className={`${styles.icon} ${styles.chatContextIcon}`}>bolt</span>
                  <span className={styles.chatContextText}>
                    +{liveUsage.prompt_tokens + liveUsage.completion_tokens} tok agora
                  </span>
                </div>
              )}
              {liveUsage?.fallback && (
                <div
                  className={`${styles.chatContextPill} ${styles.chatContextPillNotice}`}
                  title={`Selecionado: ${liveUsage.fallback.selected_model} | final: ${liveUsage.fallback.final_model}`}
                >
                  <span className={`${styles.icon} ${styles.chatContextIcon}`}>swap_horiz</span>
                  <span className={styles.chatContextText}>
                    final {liveUsage.fallback.final_model}
                  </span>
                  <span className={styles.chatContextReason}>
                    {fallbackReasonLabel(liveUsage.fallback.reason)}
                  </span>
                </div>
              )}
              </>
  )
}
