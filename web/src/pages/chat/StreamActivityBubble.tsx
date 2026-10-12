import { Stack } from '@/components/ui/legacy'
import type { ContextProgressEvent, RuntimeStateEvent, SubagentGroupEvent } from '../../api'
import { AgentActivityCard, type AgentActivityStatus } from '../../components/chat/AgentActivityCard'
import { subagentGroupDetail, type TimedSubagentGroup } from '../../components/chat/subagentGroups'
import { AgentBubble } from './AgentBubble'

function groupStatus(group: SubagentGroupEvent): AgentActivityStatus {
  const states = group.activities.map((activity) => activity.state)
  if (states.some((state) => state === 'failed')) return 'failed'
  if (states.some((state) => state === 'permission-timeout')) return 'permission-timeout'
  if (states.some((state) => state === 'canceled')) return 'canceled'
  if (states.some((state) => state === 'stalled')) return 'stalled'
  if (states.length > 0 && states.every((state) => state === 'done')) return 'done'
  return 'running'
}

/** Cartões de progresso do turno em andamento (contexto, subagentes, runtime). */
export function StreamActivityBubble({
  streaming, contextProgress, subagentGroups, runtimeStates, heavyStreamingReason, streamNowMs,
}: {
  streaming: boolean
  contextProgress: ContextProgressEvent | null
  subagentGroups: TimedSubagentGroup[]
  runtimeStates: RuntimeStateEvent[]
  heavyStreamingReason: string | null
  streamNowMs: number
}) {
  if (!(streaming && (contextProgress || subagentGroups.length > 0 || runtimeStates.length > 0 || heavyStreamingReason))) {
    return null
  }
  return (
                <AgentBubble compact>
                  <Stack gap="xs">
                    {heavyStreamingReason && (
                      <AgentActivityCard
                        title="Iteração pesada"
                        status="warning"
                        detail={`${heavyStreamingReason}. Considere usar Rápido para limitar a próxima rodada.`}
                      />
                    )}
                    {contextProgress && (
                      <AgentActivityCard
                        title={contextProgress.label}
                        status="running"
                        detail={
                          contextProgress.percent != null
                            ? `${contextProgress.percent}% do contexto preparado`
                            : contextProgress.limit_value != null && contextProgress.current_value != null
                              ? `${contextProgress.current_value.toLocaleString()} de ${contextProgress.limit_value.toLocaleString()} itens`
                              : 'Preparando contexto para o modelo'
                        }
                      />
                    )}
                    {subagentGroups.map((group) => (
                      <AgentActivityCard
                        key={group.parent_turn_id ?? group.label}
                        title={group.label}
                        status={groupStatus(group)}
                        detail={subagentGroupDetail(group, streamNowMs)}
                        activities={group.activities}
                      />
                    ))}
                    {runtimeStates.map((state, index) => (
                      <AgentActivityCard
                        key={`${state.state}-${index}`}
                        title={state.label}
                        status={state.state === 'failed' ? 'failed' : state.state}
                        detail={state.detail || (state.terminal ? 'Estado final recebido do runtime' : 'Aguardando novos eventos')}
                      />
                    ))}
                  </Stack>
                </AgentBubble>
  )
}
