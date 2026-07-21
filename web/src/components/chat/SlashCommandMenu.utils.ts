export function shouldOpenSlashCommands(value: string, caret: number): boolean {
  if (caret <= 0 || value[caret - 1] !== '/') return false
  return caret === 1 || value[caret - 2] === '\n'
}

export function slashCommandQuery(value: string, caret: number): string {
  const beforeCaret = value.slice(0, caret)
  const slash = Math.max(beforeCaret.lastIndexOf('\n/'), beforeCaret.startsWith('/') ? 0 : -1)
  const start = slash === 0 ? 1 : slash + 2
  return start > 0 ? beforeCaret.slice(start).trim().toLowerCase() : ''
}
