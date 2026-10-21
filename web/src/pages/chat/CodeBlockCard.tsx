import { useState } from 'react'
import styles from '../../components/chat.module.css'

export function CodeBlockCard({
  code,
  language,
}: {
  code: string
  language: string
}) {
  const [copied, setCopied] = useState(false)
  const normalizedLanguage = language.toLowerCase()
  const label = normalizedLanguage === 'sql'
    ? 'Consulta pronta · SQL'
    : `Código · ${normalizedLanguage.toUpperCase()}`

  async function handleCopy() {
    try {
      await navigator.clipboard?.writeText(code)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1400)
    } catch {
      /* clipboard pode estar bloqueado */
    }
  }

  return (
    <div className={styles.codeBlockCard}>
      <div className={styles.codeBlockHeader}>
        <span>{label}</span>
        <button type="button" onClick={handleCopy}>
          <span className={styles.icon}>{copied ? 'check' : 'content_copy'}</span>
          {copied ? 'copiado' : 'copiar'}
        </button>
      </div>
      <pre>
        <code className={`language-${normalizedLanguage}`}>
          {normalizedLanguage === 'sql' ? renderSqlTokens(code) : code}
        </code>
      </pre>
    </div>
  )
}

const SQL_KEYWORDS = new Set([
  'select', 'from', 'where', 'join', 'inner', 'left', 'right', 'full', 'outer',
  'on', 'and', 'or', 'as', 'group', 'by', 'order', 'having', 'limit', 'offset',
  'insert', 'into', 'update', 'delete', 'values', 'set', 'case', 'when', 'then',
  'else', 'end', 'distinct', 'union', 'all', 'count', 'sum', 'avg', 'min', 'max',
])

function renderSqlTokens(code: string): React.ReactNode[] {
  const tokenPattern = /(--.*? $|'(?:''|[^'])*'|:[a-zA-Z_][\w]*|\b\d+(?:\.\d+)?\b|\b[a-zA-Z_][\w]*\b)/gm
  const nodes: React.ReactNode[] = []
  let lastIndex = 0
  let tokenIndex = 0

  for (const match of code.matchAll(tokenPattern)) {
    const value = match[0]
    const index = match.index ?? 0
    if (index > lastIndex) nodes.push(code.slice(lastIndex, index))

    const lower = value.toLowerCase()
    const className = value.startsWith('--')
      ? styles.sqlComment
      : value.startsWith("'")
        ? styles.sqlString
        : value.startsWith(':')
          ? styles.sqlParam
          : /^\d/.test(value)
            ? styles.sqlNumber
            : SQL_KEYWORDS.has(lower)
              ? styles.sqlKeyword
              : undefined

    nodes.push(className ? <span className={className} key={tokenIndex}>{value}</span> : value)
    tokenIndex += 1
    lastIndex = index + value.length
  }

  if (lastIndex < code.length) nodes.push(code.slice(lastIndex))
  return nodes
}
