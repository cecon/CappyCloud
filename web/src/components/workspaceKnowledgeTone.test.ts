import { describe, expect, it } from 'vitest'
import { graphTone, memoryTone, timeAgo } from './workspaceKnowledgeTone'

const NOW = Date.parse('2026-09-25T12:00:00Z')

describe('workspaceKnowledgeTone', () => {
  it('diz quando o grafo precisa ser atualizado', () => {
    expect(graphTone({ state: 'never_built' }, NOW)).toMatchObject({ text: 'Grafo: nunca gerado', color: 'gray' })
    expect(graphTone({ state: 'done', behind: 12 }, NOW)).toMatchObject({ text: 'Grafo: 12 commits novos', color: 'yellow' })
    expect(graphTone({ state: 'done', behind: 1 }, NOW).text).toBe('Grafo: 1 commit novo')
    expect(graphTone({ state: 'done', missing: ['proteus'], behind: 0 }, NOW).text).toBe('Grafo: falta proteus')
    expect(graphTone({ state: 'partial', error: 'boom' }, NOW)).toMatchObject({ color: 'red', title: 'boom' })
    expect(graphTone({ state: 'done', running: true }, NOW).text).toBe('Grafo: gerando…')
    expect(graphTone({ state: 'done', behind: 0, finished_at: '2026-09-25T09:00:00Z' }, NOW)).toMatchObject({
      text: 'Grafo: atualizado há 3 h',
      color: 'green',
    })
    expect(graphTone({ available: false, error: 'x' }, NOW).text).toBe('Grafo: sandbox fora')
  })

  it('mostra se a memória está viva e em uso', () => {
    expect(memoryTone({ available: false, total: 0, last_at: null, error: 'sem AGENTMEMORY_URL' }, NOW)).toMatchObject({
      text: 'Memória: indisponível',
      color: 'red',
    })
    expect(memoryTone({ available: true, total: 0, last_at: null, error: null }, NOW).text).toBe('Memória: vazia')
    expect(memoryTone({ available: true, total: 14, last_at: '2026-09-25T11:30:00Z', error: null }, NOW).text).toBe(
      'Memória: 14 · há 30 min',
    )
  })

  it('formata o tempo', () => {
    expect(timeAgo('2026-09-22T12:00:00Z', NOW)).toBe('há 3 dias')
    expect(timeAgo(null, NOW)).toBe('')
    expect(timeAgo('2026-09-25T11:59:40Z', NOW)).toBe('agora')
  })
})
