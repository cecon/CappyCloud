import type { AgentRuntime, ContainerStatus, SandboxRuntime } from '../../api'

export type CreateState = {
  name: string
  runtime: SandboxRuntime
  agentRuntime: AgentRuntime
  image: string
  envEntries: { key: string; value: string }[]
}

export const EMPTY_CREATE: CreateState = {
  name: '',
  runtime: 'compose',
  agentRuntime: 'openclaude',
  image: '',
  envEntries: [{ key: '', value: '' }],
}

export const STATUS_COLORS: Record<ContainerStatus, string> = {
  not_created: 'gray',
  starting: 'yellow',
  running: 'blue',
  configuring: 'cyan',
  configured: 'green',
  stopped: 'gray',
  error: 'red',
}

export const STATUS_LABELS: Record<ContainerStatus, string> = {
  not_created: 'NÃO CRIADO',
  starting: 'INICIANDO',
  running: 'RODANDO',
  configuring: 'CONFIGURANDO',
  configured: 'CONFIGURADO',
  stopped: 'PARADO',
  error: 'ERRO',
}

export const STATUS_POLL_MS = 5000

export function isLiveStatus(status: ContainerStatus): boolean {
  return (
    status === 'starting' ||
    status === 'running' ||
    status === 'configuring' ||
    status === 'configured'
  )
}

export function envEntriesToRecord(entries: { key: string; value: string }[]): Record<string, string> {
  const out: Record<string, string> = {}
  for (const { key, value } of entries) {
    const k = key.trim()
    if (k) out[k] = value
  }
  return out
}
