import type { Terminal } from '@xterm/xterm'
import type { TerminalLine } from '../terminalLinks'

export function decodeBase64(data: string): Uint8Array {
  return Uint8Array.from(atob(data), (c) => c.charCodeAt(0))
}

export function visibleLines(term: Terminal): TerminalLine[] {
  const buffer = term.buffer.active
  const lines: TerminalLine[] = []
  const start = Math.max(0, buffer.length - 300)
  for (let i = start; i < buffer.length; i++) {
    const line = buffer.getLine(i)
    if (line) lines.push({ text: line.translateToString(false), wrapped: line.isWrapped })
  }
  return lines
}

export function openLink(url: string) {
  window.open(url, '_blank', 'noopener,noreferrer')
}
