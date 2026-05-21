'use strict'

function lineNumberFromIndex(content, index) {
  return content.slice(0, index).split(/\r?\n/).length
}

function trimmedSignature(raw, max = 140) {
  return raw.replace(/\s+/g, ' ').trim().slice(0, max)
}

function stableHash(value) {
  let hash = 5381
  for (let i = 0; i < value.length; i += 1) {
    hash = ((hash << 5) + hash) ^ value.charCodeAt(i)
  }
  return (hash >>> 0).toString(36)
}

function readBalancedExpression(content, startIndex, openChar = '{', closeChar = '}') {
  if (content[startIndex] !== openChar) return ''
  let depth = 0
  let quote = ''
  let escaped = false
  for (let index = startIndex; index < content.length; index += 1) {
    const char = content[index]
    if (quote) {
      if (escaped) {
        escaped = false
      } else if (char === '\\') {
        escaped = true
      } else if (char === quote) {
        quote = ''
      }
      continue
    }
    if (char === '"' || char === "'" || char === '`') {
      quote = char
      continue
    }
    if (char === openChar) depth += 1
    if (char === closeChar) {
      depth -= 1
      if (depth === 0) return content.slice(startIndex + 1, index)
    }
  }
  return ''
}

function splitTopLevelArgs(raw) {
  const args = []
  let start = 0
  let parenDepth = 0
  let braceDepth = 0
  let bracketDepth = 0
  let quote = ''
  let escaped = false

  for (let index = 0; index < raw.length; index += 1) {
    const char = raw[index]
    if (quote) {
      if (escaped) {
        escaped = false
      } else if (char === '\\') {
        escaped = true
      } else if (char === quote) {
        quote = ''
      }
      continue
    }
    if (char === '"' || char === "'" || char === '`') {
      quote = char
      continue
    }
    if (char === '(') parenDepth += 1
    if (char === ')') parenDepth = Math.max(0, parenDepth - 1)
    if (char === '{') braceDepth += 1
    if (char === '}') braceDepth = Math.max(0, braceDepth - 1)
    if (char === '[') bracketDepth += 1
    if (char === ']') bracketDepth = Math.max(0, bracketDepth - 1)
    if (char === ',' && parenDepth === 0 && braceDepth === 0 && bracketDepth === 0) {
      args.push(raw.slice(start, index).trim())
      start = index + 1
    }
  }

  const last = raw.slice(start).trim()
  if (last) args.push(last)
  return args
}

function escapeRegExp(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

function humanizeComponentName(name) {
  return name
    .split('.')
    .pop()
    .replace(/([a-zà-ÿ])([A-Z])/g, '$1 $2')
    .replace(/\s+/g, ' ')
    .trim()
}

function decodeXmlEntities(value) {
  return value
    .replace(/&amp;/g, '&')
    .replace(/&quot;/g, '"')
    .replace(/&apos;/g, "'")
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
}

function humanizeIdentifier(value) {
  return decodeXmlEntities(value || '')
    .replace(/:[A-Za-z_]\w*$/, '')
    .replace(/^(bt|btn|tv|txt|edt|cmb|chk|rb|label|lbl|grid|entry|button)_/i, '')
    .replace(/[_-]+/g, ' ')
    .replace(/([a-zà-ÿ])([A-Z])/g, '$1 $2')
    .replace(/\s+/g, ' ')
    .trim()
}

function xmlAttribute(raw, name) {
  const escaped = escapeRegExp(name)
  const match = new RegExp(`\\b${escaped}\\s*=\\s*["']([^"']*)["']`, 'i').exec(raw)
  return match ? decodeXmlEntities(match[1]) : ''
}

function gladeProperty(raw, names) {
  for (const name of names) {
    const escaped = escapeRegExp(name)
    const match = new RegExp(`<property\\s+name=["']${escaped}["'][^>]*>([\\s\\S]*?)<\\/property>`, 'i').exec(raw)
    if (!match) continue
    const value = decodeXmlEntities(match[1].replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim())
    if (value) return value
  }
  return ''
}

function gladeSignals(raw) {
  const signals = []
  for (const match of raw.matchAll(/<signal\b([^>]*)\/?>/gi)) {
    const attrs = match[1] || ''
    const handler = xmlAttribute(attrs, 'handler')
    if (!handler) continue
    signals.push({
      name: xmlAttribute(attrs, 'name') || 'signal',
      handler,
    })
  }
  return signals
}

module.exports = {
  decodeXmlEntities,
  escapeRegExp,
  gladeProperty,
  gladeSignals,
  humanizeComponentName,
  humanizeIdentifier,
  lineNumberFromIndex,
  readBalancedExpression,
  splitTopLevelArgs,
  stableHash,
  trimmedSignature,
  xmlAttribute,
}
