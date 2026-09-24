import { useEffect, useRef, useState } from 'react'
import { FitAddon } from '@xterm/addon-fit'
import { Terminal } from '@xterm/xterm'
import '@xterm/xterm/css/xterm.css'
import { Button, Group, Modal, Text } from '@/components/ui/legacy'
import {
  closeSandboxTerminal,
  getToken,
  openSandboxTerminal,
  resizeSandboxTerminal,
  sendSandboxTerminalInput,
  streamSandboxTerminal,
  type Sandbox,
} from '../api'

type Status = 'connecting' | 'open' | 'closed' | 'error'

const STATUS_TEXT: Record<Status, string> = {
  connecting: 'Conectando…',
  open: 'Conectado',
  closed: 'Sessão encerrada',
  error: 'Erro',
}

function decodeBase64(data: string): Uint8Array {
  return Uint8Array.from(atob(data), (c) => c.charCodeAt(0))
}

/**
 * Terminal web da sandbox (super admin). Serve para o `claude login` e para
 * diagnóstico; o shell roda como o usuário do container da sandbox.
 */
export function SandboxTerminalModal({ sandbox, onClose }: { sandbox: Sandbox; onClose: () => void }) {
  return (
    <Modal opened onClose={onClose} title={`Terminal · ${sandbox.name}`} size="xl">
      <TerminalView sandbox={sandbox} />
    </Modal>
  )
}

function TerminalView({ sandbox }: { sandbox: Sandbox }) {
  const containerRef = useRef<HTMLDivElement>(null)
  const sendRef = useRef<(data: string) => void>(() => {})
  const [status, setStatus] = useState<Status>('connecting')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const token = getToken()
    const container = containerRef.current
    if (!token || !container) return
    const term = new Terminal({
      cursorBlink: true,
      fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Consolas, monospace',
      fontSize: 13,
      theme: { background: '#141210' },
    })
    const fit = new FitAddon()
    term.loadAddon(fit)
    term.open(container)
    fit.fit()

    const abort = new AbortController()
    let terminalId: string | null = null
    let exited = false
    let pending = ''
    let flushTimer: number | undefined
    let sending = Promise.resolve()

    // Junta as teclas por alguns ms e envia em ordem (um POST por lote).
    const send = (data: string) => {
      pending += data
      if (flushTimer !== undefined) return
      flushTimer = window.setTimeout(() => {
        flushTimer = undefined
        const batch = pending
        pending = ''
        if (!terminalId || !batch) return
        const id = terminalId
        sending = sending
          .then(() => sendSandboxTerminalInput(token, sandbox.id, id, batch))
          .then(() => undefined)
          .catch((err: unknown) => setError(err instanceof Error ? err.message : String(err)))
      }, 25)
    }
    sendRef.current = send
    const inputListener = term.onData(send)

    let resizeTimer: number | undefined
    const observer = new ResizeObserver(() => {
      fit.fit()
      window.clearTimeout(resizeTimer)
      resizeTimer = window.setTimeout(() => {
        if (terminalId && !exited) {
          void resizeSandboxTerminal(token, sandbox.id, terminalId, { cols: term.cols, rows: term.rows }).catch(
            () => undefined,
          )
        }
      }, 150)
    })
    observer.observe(container)

    const onEvent = (event: Parameters<Parameters<typeof streamSandboxTerminal>[3]>[0]) => {
      if (event.type === 'output') {
        term.write(decodeBase64(event.data))
        return
      }
      exited = true
      setStatus('closed')
      term.write(`\r\n\x1b[2m[sessão encerrada, código ${event.code}]\x1b[0m\r\n`)
    }

    void (async () => {
      try {
        terminalId = await openSandboxTerminal(token, sandbox.id, { cols: term.cols, rows: term.rows })
        setStatus('open')
        term.focus()
        // O stream pode cair (proxy, rede): reconecta; o sandbox guarda a saída do intervalo.
        for (let attempt = 0; !exited && !abort.signal.aborted && attempt < 5; attempt++) {
          try {
            await streamSandboxTerminal(token, sandbox.id, terminalId, onEvent, abort.signal)
            attempt = 0
          } catch (err) {
            if (abort.signal.aborted) return
            if (attempt === 4) throw err
          }
          if (!exited) await new Promise((resolve) => setTimeout(resolve, 1000))
        }
      } catch (err) {
        if (abort.signal.aborted) return
        setStatus('error')
        setError(err instanceof Error ? err.message : String(err))
      }
    })()

    return () => {
      abort.abort()
      observer.disconnect()
      inputListener.dispose()
      window.clearTimeout(flushTimer)
      window.clearTimeout(resizeTimer)
      if (terminalId && !exited) void closeSandboxTerminal(token, sandbox.id, terminalId).catch(() => undefined)
      term.dispose()
    }
  }, [sandbox.id])

  return (
    <div style={{ display: 'grid', gap: 10 }}>
      <Group justify="space-between" wrap="wrap" gap="sm">
        <Text size="sm" c="dimmed">
          {STATUS_TEXT[status]}. Para conectar o Claude CLI, rode <code>claude login</code> e siga o link.
        </Text>
        <Button size="xs" variant="default" disabled={status !== 'open'} onClick={() => sendRef.current('claude login\r')}>
          Rodar claude login
        </Button>
      </Group>
      {error && (
        <Text size="sm" c="red" role="alert">
          {error}
        </Text>
      )}
      <div
        ref={containerRef}
        style={{ height: 'min(60dvh, 520px)', background: '#141210', borderRadius: 6, padding: 6, overflow: 'hidden' }}
      />
    </div>
  )
}
