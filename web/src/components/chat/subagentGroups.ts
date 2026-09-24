import type { SubagentGroupEvent } from '../../api'

/** Grupo de subagente com o tempo medido no navegador (o evento não traz horário). */
export type TimedSubagentGroup = SubagentGroupEvent & { startedAtMs: number; finishedAtMs: number | null }

const FINAL_STATES = new Set(['done', 'failed', 'canceled', 'permission-timeout'])

function isFinished(group: SubagentGroupEvent): boolean {
  return group.activities.length > 0 && group.activities.every((activity) => FINAL_STATES.has(activity.state))
}

/** Substitui o grupo de mesma chave, preservando quando ele começou. */
export function mergeSubagentGroup(
  prev: TimedSubagentGroup[],
  group: SubagentGroupEvent,
  nowMs: number,
): TimedSubagentGroup[] {
  const key = group.parent_turn_id ?? group.label
  const previous = prev.find((item) => (item.parent_turn_id ?? item.label) === key)
  const startedAtMs = previous?.startedAtMs ?? nowMs
  const finishedAtMs = isFinished(group) ? (previous?.finishedAtMs ?? nowMs) : null
  const others = prev.filter((item) => (item.parent_turn_id ?? item.label) !== key)
  return [...others, { ...group, startedAtMs, finishedAtMs }]
}

function formatDuration(ms: number): string {
  const seconds = Math.max(0, Math.round(ms / 1000))
  if (seconds < 60) return `${seconds}s`
  return `${Math.floor(seconds / 60)}m${String(seconds % 60).padStart(2, '0')}s`
}

/** "3 atividades · rodando há 12s" / "5 atividades · levou 40s". */
export function subagentGroupDetail(group: TimedSubagentGroup, nowMs: number): string {
  const total = group.activities.length
  const count = `${total} ${total === 1 ? 'atividade' : 'atividades'}`
  if (group.finishedAtMs !== null) return `${count} · levou ${formatDuration(group.finishedAtMs - group.startedAtMs)}`
  return `${count} · rodando há ${formatDuration(nowMs - group.startedAtMs)}`
}
