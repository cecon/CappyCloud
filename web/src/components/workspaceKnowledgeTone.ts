import type { WorkspaceKnowledgeSummary } from '../api'

export type Tone = { text: string; color: string; title?: string }

export function timeAgo(iso?: string | null, now = Date.now()): string {
  if (!iso) return ''
  const minutes = Math.max(0, Math.round((now - Date.parse(iso)) / 60_000))
  if (minutes < 1) return 'agora'
  if (minutes < 60) return `há ${minutes} min`
  const hours = Math.round(minutes / 60)
  if (hours < 48) return `há ${hours} h`
  return `há ${Math.round(hours / 24)} dias`
}

/** Selo do grafo: o que o admin precisa saber para decidir se atualiza. */
export function graphTone(graph: WorkspaceKnowledgeSummary['graph'], now = Date.now()): Tone {
  if (graph.available === false) return { text: 'Grafo: sandbox fora', color: 'gray', title: graph.error }
  if (graph.running || graph.state === 'running') return { text: 'Grafo: gerando…', color: 'blue' }
  if (!graph.state || graph.state === 'never_built') return { text: 'Grafo: nunca gerado', color: 'gray' }
  if (graph.state === 'error' || graph.state === 'partial') return { text: 'Grafo: erro', color: 'red', title: graph.error }
  if (graph.missing && graph.missing.length > 0) {
    return { text: `Grafo: falta ${graph.missing.join(', ')}`, color: 'yellow' }
  }
  if (graph.behind) {
    return { text: `Grafo: ${graph.behind} commit${graph.behind > 1 ? 's' : ''} novo${graph.behind > 1 ? 's' : ''}`, color: 'yellow' }
  }
  return { text: `Grafo: atualizado ${timeAgo(graph.finished_at, now)}`.trim(), color: 'green' }
}

export function memoryTone(memory: WorkspaceKnowledgeSummary['memory'], now = Date.now()): Tone {
  if (!memory.available) return { text: 'Memória: indisponível', color: 'red', title: memory.error ?? undefined }
  if (memory.total === 0) return { text: 'Memória: vazia', color: 'gray' }
  return { text: `Memória: ${memory.total} · ${timeAgo(memory.last_at, now)}`, color: 'green' }
}
