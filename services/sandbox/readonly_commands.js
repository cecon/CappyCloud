'use strict'
// Comandos de Bash permitidos nos repositórios somente leitura do workspace.
// Esta versão do Claude Code não tem Grep/Glob: a busca é pelo Bash. Nesses
// caminhos o guard aceita só leitura (sem redirecionar para arquivo, sem
// edição in-place, sem apagar/executar). É uma barreira contra engano do
// agente, não uma fronteira de segurança.

const READ_COMMANDS = new Set([
  'cat', 'head', 'tail', 'less', 'nl', 'wc', 'grep', 'egrep', 'fgrep', 'rg', 'find', 'ls', 'tree',
  'sed', 'awk', 'sort', 'uniq', 'cut', 'tr', 'file', 'stat', 'du', 'jq', 'diff', 'xargs', 'git',
  'echo', 'printf', 'basename', 'dirname', 'realpath', 'readlink', 'pwd', 'cd', 'true', 'test',
  'graphify',
])
// graphify só consulta o grafo do workspace; update/merge-graphs escrevem.
const GRAPHIFY_READ = new Set(['query', 'path', 'explain', 'god-nodes', 'affected'])
const GIT_READ = new Set(['log', 'show', 'grep', 'ls-files', 'blame', 'diff', 'rev-parse', 'cat-file', 'ls-tree', 'status', 'describe'])
const FORBIDDEN = [
  /(^|\s)-(delete|exec|execdir|ok|okdir|fprint|fprintf|fls)(\s|$)/, // find
  /\bsystem\s*\(/, // awk system()
]
// Redirecionamentos que não escrevem arquivo: 2>&1, >/dev/null, 2>/dev/null, &>/dev/null.
const HARMLESS_REDIRECT = /^(>&\d|>>?\s*\/dev\/null)/

/**
 * Quebra o comando em comandos simples, respeitando aspas. `$(…)`, crase e
 * `<(…)` também separam (o comando de dentro é checado como os outros).
 * `writes` fica true se houver `>` fora de aspas que não seja inofensivo.
 */
function splitCommand(command) {
  const segments = []
  let buffer = ''
  let quote = null
  let writes = false
  const flush = () => {
    if (buffer.trim()) segments.push(buffer.trim())
    buffer = ''
  }
  for (let i = 0; i < command.length; i++) {
    const char = command[i]
    const next = command[i + 1]
    if (quote === "'") {
      if (char === "'") quote = null
      buffer += char
      continue
    }
    if (char === '\\') {
      buffer += char + (next ?? '')
      i++
      continue
    }
    if ((char === '$' || char === '<') && next === '(') {
      flush()
      i++
      continue
    }
    if (char === '`') {
      flush()
      continue
    }
    if (quote === '"') {
      if (char === '"') quote = null
      buffer += char
      continue
    }
    if (char === "'" || char === '"') {
      quote = char
      buffer += char
    } else if ('|;&\n()'.includes(char)) {
      if (char === '&' && next === '>') continue // &>arquivo: o '>' decide abaixo
      flush()
    } else if (char === '>') {
      const match = command.slice(i).match(HARMLESS_REDIRECT)
      if (match) {
        i += match[0].length - 1
        buffer = buffer.replace(/\d$/, '')
      } else {
        writes = true
      }
    } else {
      buffer += char
    }
  }
  flush()
  return { segments, writes }
}

/** True se o comando só lê arquivos (lista de programas + sem escrita). */
function isReadOnlyCommand(command) {
  const text = String(command || '')
  if (FORBIDDEN.some((pattern) => pattern.test(text))) return false
  const { segments, writes } = splitCommand(text)
  if (writes) return false
  for (const segment of segments) {
    const words = segment.split(/\s+/).filter((word) => !/^[A-Za-z_][A-Za-z0-9_]*=/.test(word))
    const [program, ...args] = words
    if (!program) continue
    const name = program.replace(/^["']|["']$/g, '').split('/').pop()
    if (!READ_COMMANDS.has(name)) return false
    // sed -i / -i.bak / -ni / --in-place editam o arquivo.
    if (name === 'sed' && args.some((arg) => /^-[a-zA-Z]*i/.test(arg) || arg.startsWith('--in-place'))) return false
    if (name === 'git') {
      const sub = args.find((arg) => !arg.startsWith('-') && !arg.startsWith('/'))
      if (!sub || !GIT_READ.has(sub)) return false
    }
    if (name === 'graphify' && !GRAPHIFY_READ.has(args.find((arg) => !arg.startsWith('-')))) return false
    if (name === 'xargs') {
      const target = args.find((arg) => !arg.startsWith('-'))
      if (!target || target === 'xargs' || !READ_COMMANDS.has(target.split('/').pop())) return false
    }
  }
  return true
}

module.exports = { isReadOnlyCommand, splitCommand }
