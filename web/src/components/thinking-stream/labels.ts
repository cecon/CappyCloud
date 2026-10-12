import { knowledgeKind, knowledgeLabel, knowledgeSummary } from '../chat/knowledgeTools'
import type { ThoughtStep } from './types'

export const SUBAGENT_TOOLS = new Set(['agent', 'task'])

/** Nome do passo para o usuário: Agent/Task é um subagente; grafo e memória pelo nome. */
export function displayToolName(name: string, raw = ''): string {
  const kind = knowledgeKind(name, raw)
  if (kind) return knowledgeLabel(kind).name
  return SUBAGENT_TOOLS.has(name.toLowerCase()) ? 'Subagente' : name
}

export function summarizeToolInput(name: string, raw: string): string {
  const kind = knowledgeKind(name, raw)
  if (kind) return knowledgeSummary(kind, raw)
  let parsed: Record<string, unknown> | null = null
  try {
    parsed = JSON.parse(raw)
  } catch {
    parsed = null
  }
  if (!parsed) return raw.slice(0, 80)

  const lname = name.toLowerCase()
  if (SUBAGENT_TOOLS.has(lname)) {
    return String(parsed.description ?? parsed.subagent_type ?? '')
  }
  if (lname === 'grep') {
    const pattern = String(parsed.pattern ?? '')
    const path = String(parsed.path ?? parsed.glob ?? '')
    return path ? `"${pattern}" em ${path}` : `"${pattern}"`
  }
  if (lname === 'read') {
    return String(parsed.file_path ?? parsed.path ?? raw)
  }
  if (lname === 'bash') {
    return String(parsed.command ?? '')
  }
  if (lname === 'glob') {
    return String(parsed.pattern ?? '')
  }
  if (lname === 'edit' || lname === 'write') {
    return String(parsed.file_path ?? parsed.path ?? '')
  }
  if (lname === 'webfetch' || lname === 'web_fetch') {
    return String(parsed.url ?? '')
  }
  const firstStrVal = Object.values(parsed).find(
    (v) => typeof v === 'string' && (v as string).length > 0,
  )
  return firstStrVal ? String(firstStrVal).slice(0, 80) : ''
}

export function describeActiveStep(step: ThoughtStep): string {
  if (step.kind === 'phase') return `${step.label}…`
  if (step.kind === 'text') {
    const trimmed = step.content.trim().replace(/\s+/g, ' ')
    return trimmed.length > 80 ? `${trimmed.slice(0, 80)}…` : trimmed || 'Pensando…'
  }
  const lname = step.name.toLowerCase()
  const summary = summarizeToolInput(step.name, step.input)
  const kind = knowledgeKind(step.name, step.input)
  const verb = kind
    ? knowledgeLabel(kind).verb
    : lname === 'grep'
      ? 'Pesquisando'
      : lname === 'read'
        ? 'Lendo'
        : lname === 'bash'
          ? 'Executando'
          : lname === 'glob'
            ? 'Listando'
            : lname === 'edit' || lname === 'write'
              ? 'Editando'
              : lname === 'webfetch' || lname === 'web_fetch'
                ? 'Buscando'
                : SUBAGENT_TOOLS.has(lname)
                  ? 'Subagente:'
                  : step.name
  return summary ? `${verb} ${summary}` : verb
}

export function formatElapsed(ms: number): string {
  if (ms < 1000) return `${ms}ms`
  const s = ms / 1000
  if (s < 60) return `${s.toFixed(1)}s`
  const m = Math.floor(s / 60)
  return `${m}m${Math.round(s - m * 60)}s`
}

export function countByTool(steps: ThoughtStep[]): Array<[string, number]> {
  const counts: Record<string, number> = {}
  for (const s of steps) {
    if (s.kind !== 'tool') continue
    const name = displayToolName(s.name, s.input)
    counts[name] = (counts[name] ?? 0) + 1
  }
  return Object.entries(counts).sort((a, b) => b[1] - a[1])
}

export function activeCoordinatorLabel(steps: ThoughtStep[], idleMs: number): string {
  const runningTools = steps.filter(
    (s): s is Extract<ThoughtStep, { kind: 'tool' }> => s.kind === 'tool' && !s.done,
  )
  if (runningTools.length > 1) {
    return `Aguardando ${runningTools.length} ferramentas em paralelo`
  }
  if (runningTools.length === 1) {
    return `Aguardando ${runningTools[0].name}`
  }
  if (idleMs < 8_000) return 'Pensando'
  if (idleMs < 35_000) return 'Consolidando evidências'
  if (idleMs < 90_000) return 'Aguardando coordenador'
  return 'Preparando resposta final'
}

export function activeHeaderLabel(steps: ThoughtStep[], idleMs: number): string {
  const runningTools = steps.filter(
    (s): s is Extract<ThoughtStep, { kind: 'tool' }> => s.kind === 'tool' && !s.done,
  )
  if (runningTools.length > 1) return `${runningTools.length} ferramentas trabalhando em paralelo`
  if (runningTools.length === 1) return describeActiveStep(runningTools[0])
  const openPhase = steps.find((s) => s.kind === 'phase' && !s.done)
  if (openPhase) return describeActiveStep(openPhase)
  if (idleMs < 8_000) return 'Pensando…'
  if (idleMs < 35_000) return 'Cruzando resultados das ferramentas…'
  if (idleMs < 90_000) return 'Aguardando o coordenador continuar…'
  return 'Aguardando a resposta final…'
}
