import { useEffect, useRef, useState } from 'react'
import { ClipboardAddon } from '@xterm/addon-clipboard'
import { FitAddon } from '@xterm/addon-fit'
import { WebLinksAddon } from '@xterm/addon-web-links'
import { Terminal } from '@xterm/xterm'
import '@xterm/xterm/css/xterm.css'
import { Button, Group, Modal, Text, TextInput } from '@/components/ui/legacy'
import {
  closeSandboxTerminal,
  getToken,
  openSandboxTerminal,
  resizeSandboxTerminal,
  sendSandboxTerminalInput,
  streamSandboxTerminal,
  type Sandbox,
  type SandboxTerminalEvent,
} from '../api'
import { findLastUrl, type TerminalLine } from './terminalLinks'

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

function visibleLines(term: Terminal): TerminalLine[] {
  const buffer = term.buffer.active
  const lines: TerminalLine[] = []
  const start = Math.max(0, buffer.length - 300)
  for (let i = start; i < buffer.length; i++) {
    const line = buffer.getLine(i)
    if (line) lines.push({ text: line.translateToString(false), wrapped: line.isWrapped })
  }
  return lines
}

function openLink(url: string) {
  window.open(url, '_blank', 'noopener,noreferrer')
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

type Controls = {
  send: (data: string) => void
  paste: (text: string) => void
  selection: () => string
  focus: () => void
}

function TerminalView({ sandbox }: { sandbox: Sandbox }) {
  const containerRef = useRef<HTMLDivElement>(null)
  const controls = useRef<Controls | null>(null)
  const [status, setStatus] = useState<Status>('connecting')
  const [error, setError] = useState<string | null>(null)
  const [link, setLink] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [menu, setMenu] = useState<{ x: number; y: number } | null>(null)
  const [manual, setManual] = useState('')

  const flash = (text: string) => {
    setNotice(text)
    window.setTimeout(() => setNotice(null), 2000)
  }

  const copy = async (text: string, label: string) => {
    if (!text) return
    try {
      await navigator.clipboard.writeText(text)
      flash(`${label} copiado.`)
    } catch {
      setError('O navegador bloqueou a cópia; selecione o texto e use Ctrl+C.')
    }
  }

  const pasteFromClipboard = async () => {
    try {
      const text = await navigator.clipboard.readText()
      if (text) controls.current?.paste(text)
      controls.current?.focus()
    } catch {
      setError('O navegador bloqueou a leitura da área de transferência; use o campo "Colar no terminal".')
    }
  }

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
    // Links clicáveis e a cópia pedida pelo próprio programa (ex.: "c to copy" do Claude CLI).
    term.loadAddon(new WebLinksAddon((_event, uri) => openLink(uri)))
    term.loadAddon(new ClipboardAddon())
    term.open(container)
    fit.fit()

    const abort = new AbortController()
    let terminalId: string | null = null
    let exited = false
    let pending = ''
    let flushTimer: number | undefined
    let linkTimer: number | undefined
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
    controls.current = {
      send,
      paste: (text) => term.paste(text),
      selection: () => term.getSelection(),
      focus: () => term.focus(),
    }
    const inputListener = term.onData(send)

    // Ctrl+C com seleção copia (sem seleção segue como interrupção); Ctrl+V cola.
    term.attachCustomKeyEventHandler((event) => {
      if (event.type !== 'keydown' || !(event.ctrlKey || event.metaKey)) return true
      const key = event.key.toLowerCase()
      if (key === 'c' && (event.shiftKey || term.hasSelection())) {
        void navigator.clipboard.writeText(term.getSelection()).catch(() => undefined)
        term.clearSelection()
        event.preventDefault()
        return false
      }
      // Deixa o navegador disparar o "paste" nativo, que o xterm envia ao shell.
      if (key === 'v') return false
      return true
    })

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

    // Recarregar/fechar a aba não desmonta o React: fecha o terminal no sandbox mesmo assim.
    const closeOnLeave = () => {
      if (terminalId && !exited) void closeSandboxTerminal(token, sandbox.id, terminalId, true).catch(() => undefined)
    }
    window.addEventListener('pagehide', closeOnLeave)

    const onEvent = (event: SandboxTerminalEvent) => {
      if (event.type === 'output') {
        term.write(decodeBase64(event.data), () => {
          window.clearTimeout(linkTimer)
          linkTimer = window.setTimeout(() => setLink(findLastUrl(visibleLines(term), term.cols)), 200)
        })
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
      window.removeEventListener('pagehide', closeOnLeave)
      observer.disconnect()
      inputListener.dispose()
      window.clearTimeout(flushTimer)
      window.clearTimeout(resizeTimer)
      window.clearTimeout(linkTimer)
      if (terminalId && !exited) void closeSandboxTerminal(token, sandbox.id, terminalId).catch(() => undefined)
      controls.current = null
      term.dispose()
    }
  }, [sandbox.id])

  const open = status === 'open'
  const submitManual = () => {
    if (!manual) return
    controls.current?.paste(manual)
    // Enter em outro envio: grudado no fim da colagem, o shell/Claude CLI descarta.
    window.setTimeout(() => controls.current?.send('\r'), 200)
    setManual('')
    controls.current?.focus()
  }

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1fr)', gap: 10, minWidth: 0 }} onClick={() => setMenu(null)}>
      <Group justify="space-between" wrap="wrap" gap="sm">
        <Text size="sm" c="dimmed" style={{ overflowWrap: 'anywhere', minWidth: 0 }}>
          {STATUS_TEXT[status]}. Para conectar o Claude CLI, rode <code>claude login</code>, abra o link e cole o código.
        </Text>
        <Group gap="xs" wrap="wrap">
          <Button size="xs" variant="default" disabled={!open} onClick={() => controls.current?.send('claude login\r')}>
            Rodar claude login
          </Button>
          <Button size="xs" variant="default" disabled={!open} onClick={() => void pasteFromClipboard()}>
            Colar
          </Button>
        </Group>
      </Group>

      {link && (
        <Group gap="xs" wrap="nowrap" style={{ minWidth: 0 }}>
          <Text size="xs" c="dimmed" style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1 }} title={link}>
            Link: {link}
          </Text>
          <Button size="xs" onClick={() => openLink(link)}>
            Abrir link
          </Button>
          <Button size="xs" variant="default" onClick={() => void copy(link, 'Link')}>
            Copiar link
          </Button>
        </Group>
      )}

      {(error || notice) && (
        <Text size="sm" c={error ? 'red' : 'green'} role={error ? 'alert' : 'status'}>
          {error ?? notice}
        </Text>
      )}

      <div style={{ position: 'relative' }}>
        <div
          ref={containerRef}
          onContextMenu={(event) => {
            event.preventDefault()
            const box = event.currentTarget.getBoundingClientRect()
            setMenu({ x: event.clientX - box.left, y: event.clientY - box.top })
          }}
          style={{ height: 'min(55dvh, 480px)', background: '#141210', borderRadius: 6, padding: 6, overflow: 'hidden' }}
        />
        {menu && (
          <div
            role="menu"
            style={{
              position: 'absolute',
              left: menu.x,
              top: menu.y,
              zIndex: 5,
              display: 'grid',
              minWidth: 160,
              padding: 4,
              borderRadius: 6,
              background: 'var(--popover, #221f1b)',
              border: '1px solid var(--border, #3a352e)',
              boxShadow: '0 6px 20px rgba(0,0,0,.35)',
            }}
          >
            {[
              { label: 'Copiar', run: () => void copy(controls.current?.selection() ?? '', 'Texto') },
              { label: 'Colar', run: () => void pasteFromClipboard() },
              ...(link
                ? [
                    { label: 'Abrir link', run: () => openLink(link) },
                    { label: 'Copiar link', run: () => void copy(link, 'Link') },
                  ]
                : []),
            ].map((item) => (
              <button
                key={item.label}
                type="button"
                role="menuitem"
                onClick={() => {
                  setMenu(null)
                  item.run()
                }}
                style={{
                  textAlign: 'left',
                  padding: '6px 10px',
                  border: 0,
                  borderRadius: 4,
                  background: 'transparent',
                  color: 'inherit',
                  cursor: 'pointer',
                  font: 'inherit',
                  fontSize: 13,
                }}
              >
                {item.label}
              </button>
            ))}
          </div>
        )}
      </div>

      <Group gap="xs" wrap="nowrap">
        <div style={{ flex: 1, minWidth: 0 }}>
          <TextInput
            aria-label="Colar no terminal"
            placeholder="Colar no terminal (ex.: o código do login) e Enviar"
            value={manual}
            disabled={!open}
            onChange={(event) => setManual(event.currentTarget.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter') submitManual()
            }}
          />
        </div>
        <Button size="xs" disabled={!open || !manual} onClick={submitManual}>
          Enviar
        </Button>
      </Group>
    </div>
  )
}
