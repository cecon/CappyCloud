import { describe, expect, it } from 'vitest'
import { findLastUrl, type TerminalLine } from './terminalLinks'

const COLS = 20

function screen(...rows: string[]): TerminalLine[] {
  return rows.map((text) => ({ text: text.padEnd(COLS, ' '), wrapped: false }))
}

describe('findLastUrl', () => {
  it('junta a URL quebrada na largura do terminal', () => {
    const lines = screen('Use the url below:', 'https://claude.com/c', 'ai/oauth?code=true&c', 'lient_id=9d1c', '', 'Paste code here >')
    expect(findLastUrl(lines, COLS)).toBe('https://claude.com/cai/oauth?code=true&client_id=9d1c')
  })

  it('não junta a linha seguinte quando a URL termina antes da borda', () => {
    expect(findLastUrl(screen('ver https://a.io', 'proxima'), COLS)).toBe('https://a.io')
  })

  it('segue linhas marcadas como continuação e devolve a última URL', () => {
    const lines: TerminalLine[] = [
      { text: 'https://velha.io'.padEnd(COLS), wrapped: false },
      { text: 'ok https://nova.io/'.padEnd(COLS), wrapped: false },
      { text: 'caminho', wrapped: true },
    ]
    expect(findLastUrl(lines, COLS)).toBe('https://nova.io/caminho')
  })

  it('sem URL devolve null', () => {
    expect(findLastUrl(screen('root@sandbox:~#'), COLS)).toBeNull()
  })
})
