import { describe, expect, it } from 'vitest'
import type { SubagentGroupEvent } from '../../api'
import { mergeSubagentGroup, subagentGroupDetail } from './subagentGroups'

function group(id: string, states: SubagentGroupEvent['activities'][number]['state'][]): SubagentGroupEvent {
  return {
    parent_turn_id: id,
    label: `Subagente · ${id}`,
    collapsible: true,
    activities: states.map((state, index) => ({ id: `${id}-${index}`, name: 'Bash', state, detail: '' })),
  }
}

describe('cartões de subagente', () => {
  it('mantém o início, marca o fim e mostra o tempo', () => {
    let groups = mergeSubagentGroup([], group('a', ['loading']), 1_000)
    groups = mergeSubagentGroup(groups, group('b', ['loading']), 2_000)
    groups = mergeSubagentGroup(groups, group('a', ['tool-running', 'tool-running']), 5_000)
    const running = groups.find((item) => item.parent_turn_id === 'a')!
    expect(running.startedAtMs).toBe(1_000)
    expect(subagentGroupDetail(running, 13_000)).toBe('2 atividades · rodando há 12s')

    groups = mergeSubagentGroup(groups, group('a', ['done', 'done']), 41_000)
    const finished = groups.find((item) => item.parent_turn_id === 'a')!
    expect(subagentGroupDetail(finished, 90_000)).toBe('2 atividades · levou 40s')
    expect(groups).toHaveLength(2)
  })

  it('formata minutos', () => {
    const groups = mergeSubagentGroup([], group('c', ['streaming']), 0)
    expect(subagentGroupDetail(groups[0], 125_000)).toBe('1 atividade · rodando há 2m05s')
  })
})
