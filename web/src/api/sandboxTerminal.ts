import { apiFetch, formatApiErrorPayload } from './http'

/** Estado do Claude CLI dentro da sandbox (instalado, versão, `claude login`). */
export interface SandboxClaudeStatus {
  reachable: boolean
  error?: string
  installed?: boolean
  version?: string | null
  logged_in?: boolean
  config_dir?: string
  active_turns?: number
}

export async function fetchSandboxClaudeStatus(
  token: string,
  sandboxId: string,
): Promise<SandboxClaudeStatus> {
  const res = await apiFetch(`/api/admin/sandboxes/${sandboxId}/claude-status`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || 'Falha ao consultar o Claude CLI')
  }
  return (await res.json()) as SandboxClaudeStatus
}

// ── Terminal web da sandbox (super admin) ───────────────────────────────────

/** Evento do stream do terminal: saída em base64 ou fim do shell. */
export type SandboxTerminalEvent =
  | { type: 'output'; data: string }
  | { type: 'exit'; code: number; error?: string }

async function terminalRequest(
  token: string,
  path: string,
  method: 'POST' | 'DELETE',
  body?: unknown,
  keepalive = false,
): Promise<Record<string, unknown>> {
  const res = await apiFetch(path, {
    method,
    keepalive,
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || 'Falha no terminal da sandbox')
  }
  return (await res.json()) as Record<string, unknown>
}

export async function openSandboxTerminal(
  token: string,
  sandboxId: string,
  size: { cols: number; rows: number },
): Promise<string> {
  const data = await terminalRequest(token, `/api/admin/sandboxes/${sandboxId}/terminal`, 'POST', size)
  return String(data.id)
}

export function sendSandboxTerminalInput(token: string, sandboxId: string, terminalId: string, data: string) {
  return terminalRequest(token, `/api/admin/sandboxes/${sandboxId}/terminal/${terminalId}/input`, 'POST', { data })
}

export function resizeSandboxTerminal(
  token: string,
  sandboxId: string,
  terminalId: string,
  size: { cols: number; rows: number },
) {
  return terminalRequest(token, `/api/admin/sandboxes/${sandboxId}/terminal/${terminalId}/resize`, 'POST', size)
}

/** `keepalive`: o pedido sobrevive ao fechamento/recarga da página. */
export function closeSandboxTerminal(token: string, sandboxId: string, terminalId: string, keepalive = false) {
  return terminalRequest(token, `/api/admin/sandboxes/${sandboxId}/terminal/${terminalId}`, 'DELETE', undefined, keepalive)
}

/** Lê o stream NDJSON do terminal até o shell terminar ou o `signal` abortar. */
export async function streamSandboxTerminal(
  token: string,
  sandboxId: string,
  terminalId: string,
  onEvent: (event: SandboxTerminalEvent) => void,
  signal: AbortSignal,
): Promise<void> {
  const res = await apiFetch(`/api/admin/sandboxes/${sandboxId}/terminal/${terminalId}/stream`, {
    headers: { Authorization: `Bearer ${token}` },
    signal,
  })
  if (!res.ok || !res.body) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || 'Falha ao ler o terminal')
  }
  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  for (;;) {
    const { done, value } = await reader.read()
    if (done) return
    buffer += decoder.decode(value, { stream: true })
    let newline = buffer.indexOf('\n')
    while (newline >= 0) {
      const line = buffer.slice(0, newline).trim()
      buffer = buffer.slice(newline + 1)
      if (line) onEvent(JSON.parse(line) as SandboxTerminalEvent)
      newline = buffer.indexOf('\n')
    }
  }
}
