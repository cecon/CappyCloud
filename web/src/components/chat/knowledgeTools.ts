/**
 * Consultas do agente ao conhecimento do workspace, que chegam como Bash:
 * `graphify query|explain|path|…` (grafo de código) e `curl …/memory/search|save`
 * (memória do agentmemory). O chat mostra esses passos pelo nome, não como "Bash".
 */

export type KnowledgeKind = 'graph' | 'memory_search' | 'memory_save'

const GRAPHIFY = /\bgraphify\s+(query|explain|path|god-nodes|affected)\b/
const LABELS: Record<KnowledgeKind, { name: string; verb: string }> = {
  graph: { name: 'Grafo de código', verb: 'Consultando o grafo' },
  memory_search: { name: 'Memória · busca', verb: 'Consultando a memória' },
  memory_save: { name: 'Memória · gravação', verb: 'Gravando na memória' },
}

function bashCommand(name: string, rawInput: string): string {
  if (name.toLowerCase() !== 'bash') return ''
  try {
    const parsed = JSON.parse(rawInput) as { command?: unknown }
    return typeof parsed.command === 'string' ? parsed.command : ''
  } catch {
    return ''
  }
}

export function knowledgeKind(name: string, rawInput: string): KnowledgeKind | null {
  const command = bashCommand(name, rawInput)
  if (!command) return null
  if (command.includes('/memory/save')) return 'memory_save'
  if (command.includes('/memory/search')) return 'memory_search'
  if (GRAPHIFY.test(command)) return 'graph'
  return null
}

/** O que foi perguntado ou gravado, para o resumo do passo. */
export function knowledgeSummary(kind: KnowledgeKind, rawInput: string): string {
  const command = bashCommand('bash', rawInput)
  if (kind === 'graph') {
    const match = command.match(/graphify\s+(\S+)\s+(["'])(.*?)\2/)
    return match ? `${match[1]}: ${match[3]}` : 'grafo do workspace'
  }
  if (kind === 'memory_search') {
    const match = command.match(/q=([^'"&]+)/)
    return match ? decodeURIComponent(match[1].replace(/\+/g, ' ')).trim() : ''
  }
  const match = command.match(/\\?"content\\?"\s*:\s*\\?"(.*?)\\?"\s*[,}]/)
  return match ? match[1].slice(0, 80) : ''
}

export function knowledgeLabel(kind: KnowledgeKind): { name: string; verb: string } {
  return LABELS[kind]
}
