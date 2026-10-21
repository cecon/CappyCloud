/** Linha do terminal: texto sem cortar os espaços do fim e se continua a anterior (quebra automática). */
export type TerminalLine = { text: string; wrapped: boolean }

const URL_START = /https?:\/\/\S*/g
const URL_CHARS = /^[^\s"'<>`]+/

/**
 * Último link visível no terminal, juntando as linhas em que ele foi quebrado.
 * Programas como o Claude CLI quebram a URL longa na largura do terminal
 * (quebra "de verdade", sem marcar a linha como continuação); por isso uma URL
 * que encosta na última coluna continua na linha seguinte.
 */
export function findLastUrl(lines: TerminalLine[], cols: number): string | null {
  for (let i = lines.length - 1; i >= 0; i--) {
    const matches = [...lines[i].text.matchAll(URL_START)]
    const last = matches.at(-1)
    if (!last || last.index === undefined) continue
    let url = last[0]
    let reachesEdge = last.index + url.length >= Math.min(cols, lines[i].text.length) - 1
    for (let j = i + 1; j < lines.length; j++) {
      const next = lines[j]
      if (!reachesEdge && !next.wrapped) break
      const text = reachesEdge ? next.text.replace(/^ {1,2}/, '') : next.text
      const piece = text.match(URL_CHARS)?.[0] ?? ''
      if (!piece) break
      url += piece
      reachesEdge = next.text.length - text.length + piece.length >= Math.min(cols, next.text.length) - 1
    }
    return url.replace(/[).,;]+$/, '')
  }
  return null
}
