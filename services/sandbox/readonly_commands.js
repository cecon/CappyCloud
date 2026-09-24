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
])
const GIT_READ = new Set(['log', 'show', 'grep', 'ls-files', 'blame', 'diff', 'rev-parse', 'cat-file', 'ls-tree', 'status', 'describe'])
const FORBIDDEN = [
  /(^|\s)-(delete|exec|execdir|ok|okdir|fprint|fprintf|fls)(\s|$)/, // find
  /\bsystem\s*\(/, // awk system()
  /`|\$\(/, // substituição de comando
]

function withoutHarmlessRedirects(command) {
  return command
    .replace(/\d?>&\d/g, ' ')
    .replace(/&?\d?>>?\s*\/dev\/null/g, ' ')
}

/** True se o comando só lê arquivos (lista de comandos + sem escrita). */
function isReadOnlyCommand(command) {
  const cleaned = withoutHarmlessRedirects(String(command || ''))
  if (/[<>]/.test(cleaned.replace(/<<-?\s*['"]?\w+['"]?/g, ''))) return false
  if (FORBIDDEN.some((pattern) => pattern.test(cleaned))) return false
  const segments = cleaned.split(/\|\||&&|[|;&\n]/).map((part) => part.trim()).filter(Boolean)
  for (const segment of segments) {
    const words = segment.split(/\s+/).filter((word) => !/^[A-Za-z_][A-Za-z0-9_]*=/.test(word))
    const [program, ...args] = words
    if (!program) continue
    const name = program.split('/').pop()
    if (!READ_COMMANDS.has(name)) return false
    // sed -i / -i.bak / -ni / --in-place editam o arquivo.
    if (name === 'sed' && args.some((arg) => /^-[a-zA-Z]*i/.test(arg) || arg.startsWith('--in-place'))) return false
    if (name === 'git') {
      const sub = args.find((arg) => !arg.startsWith('-') && !/^-C$/.test(arg) && !arg.startsWith('/'))
      if (!sub || !GIT_READ.has(sub)) return false
    }
    if (name === 'xargs') {
      const target = args.find((arg) => !arg.startsWith('-'))
      if (!target || !READ_COMMANDS.has(target.split('/').pop()) || target === 'xargs') return false
    }
  }
  return true
}

module.exports = { isReadOnlyCommand }
