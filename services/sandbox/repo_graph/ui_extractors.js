'use strict'

const path = require('path')
const {
  gladeProperty,
  gladeSignals,
  humanizeComponentName,
  humanizeIdentifier,
  lineNumberFromIndex,
  readBalancedExpression,
  stableHash,
  trimmedSignature,
} = require('./text')

function jsxAttribute(raw, names) {
  for (const name of names) {
    const re = new RegExp(`\\b${name}\\s*=`, 'i')
    const match = re.exec(raw)
    if (!match) continue
    let index = (match.index || 0) + match[0].length
    while (/\s/.test(raw[index] || '')) index += 1
    const char = raw[index]
    if (char === '{') return readBalancedExpression(raw, index)
    if (char === '"' || char === "'") {
      let end = index + 1
      while (end < raw.length && raw[end] !== char) end += raw[end] === '\\' ? 2 : 1
      return raw.slice(index + 1, end)
    }
  }
  return ''
}

function labelFromExpression(raw) {
  const value = raw.trim()
  if (!value) return ''
  const literal = value.match(/^['"`]([\s\S]*?)['"`]$/)
  const source = literal ? literal[1] : value
  const parts = []
  for (const match of source.matchAll(/['"`]([^'"`{}]{2,80})['"`]/g)) {
    parts.push(match[1])
  }
  const withoutCode = source
    .replace(/\$\{[^}]*\}/g, ' ')
    .replace(/[{}()[\]?:|&,+*/=<>]/g, ' ')
    .replace(/\b[A-Za-z_$][\w$]*\b/g, (word) => (/[a-záàâãéêíóôõúç]/i.test(word) ? word : ' '))
    .replace(/\s+/g, ' ')
    .trim()
  if (withoutCode && /[A-Za-zÀ-ÿ]/.test(withoutCode)) parts.push(withoutCode)
  return Array.from(new Set(parts.map((part) => part.replace(/\s+/g, ' ').trim()).filter(Boolean)))
    .slice(0, 3)
    .join(' / ')
}

function textFromJsxChildren(rawBlock) {
  const parts = []
  for (const match of rawBlock.matchAll(/>([^<>{}]{2,90})</g)) {
    const text = match[1].replace(/\s+/g, ' ').trim()
    if (/[=&|]/.test(text) || /\b(screenWidth|props|state|style)\b/.test(text)) continue
    if (/[A-Za-zÀ-ÿ]/.test(text)) parts.push(text)
  }
  return Array.from(new Set(parts)).slice(0, 3).join(' / ')
}

function findJsxOpenTagEnd(content, startIndex) {
  let braceDepth = 0
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
    if (char === '{') braceDepth += 1
    if (char === '}') braceDepth = Math.max(0, braceDepth - 1)
    if (char === '>' && braceDepth === 0) return index
  }
  return -1
}

function handlerNameFromExpression(expression) {
  const clean = expression
    .trim()
    .replace(/^this\./, '')
    .replace(/^props\./, '')
    .replace(/^ctrl\./, '')
  const simple = clean.match(/^([A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)?)$/)
  if (simple) return simple[1].split('.').pop()
  const call = clean.match(/\b([A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)?)\s*\(/)
  if (call) return call[1].split('.').pop()
  return ''
}

function gladeWidgetPriority(widgetClass, widgetId, signals) {
  const source = `${widgetClass} ${widgetId}`.toLowerCase()
  if (signals.length) return 100
  if (/button|menuitem|toolbutton|toggle|radio|check/.test(source)) return 80
  if (/treeview|liststore|grid|table|notebook/.test(source)) return 55
  if (/entry|combo|spin|calendar|textview|chooser/.test(source)) return 35
  return 0
}

function gladeTitle(content, file) {
  const title = gladeProperty(content.slice(0, 4000), ['title', 'label'])
  return title || humanizeIdentifier(path.posix.basename(file, path.posix.extname(file)))
}

function extractUiActionsFromGlade(file, content) {
  const widgetMatches = Array.from(content.matchAll(/<widget\s+class=["']([^"']+)["']\s+id=["']([^"']+)["'][^>]*>/gi))
  const candidates = []
  const seen = new Set()

  for (let index = 0; index < widgetMatches.length; index += 1) {
    const match = widgetMatches[index]
    const start = match.index || 0
    const end = widgetMatches[index + 1]?.index ?? content.indexOf('</widget>', start)
    const raw = content.slice(start, end > start ? end : Math.min(content.length, start + 3000))
    const widgetClass = match[1]
    const widgetId = match[2]
    if (/^label/i.test(widgetId) || /^GtkLabel$/i.test(widgetClass)) continue

    const signals = gladeSignals(raw)
    const priority = gladeWidgetPriority(widgetClass, widgetId, signals)
    if (priority === 0) continue

    const label =
      gladeProperty(raw, ['label', 'tooltip', 'title']) ||
      humanizeIdentifier(widgetId) ||
      humanizeComponentName(widgetClass)
    if (!label || label.length < 2) continue

    const handler = signals[0]?.handler || ''
    const line = lineNumberFromIndex(content, start)
    const id = `symbol:${file}:${line}:ui:${stableHash(`${widgetClass}:${widgetId}:${handler}`)}`
    if (seen.has(id)) continue
    seen.add(id)
    candidates.push({
      priority,
      symbol: {
        id,
        name: label.slice(0, 80),
        kind: 'ui_action',
        file_path: file,
        line,
        signature: trimmedSignature(
          `${widgetClass}${signals.length ? ` ${signals.map((signal) => `${signal.name}=${signal.handler}`).join(' ')}` : ''}`,
          220,
        ),
        exported: false,
        container: widgetClass,
        element: widgetClass,
        handler,
        handler_expression: handler,
      },
    })
  }

  return candidates
    .sort((a, b) => b.priority - a.priority || a.symbol.line - b.symbol.line)
    .slice(0, 42)
    .map((candidate) => candidate.symbol)
}

function inferPythonWidgetElement(widgetName, signalName) {
  const source = `${widgetName} ${signalName}`.toLowerCase()
  if (/^(bt|btn)_|button|click|clicked|press/.test(source)) return 'GtkButton'
  if (/tv_|grid|tree|list|row|select/.test(source)) return 'GtkTreeView'
  if (/check|toggle|radio/.test(source)) return 'GtkCheckButton'
  return 'GtkEntry'
}

function extractUiActionsFromPython(file, content) {
  const symbols = []
  const seen = new Set()
  const connectRe = /\bself\.w\.([A-Za-z_]\w*)\.connect\(\s*['"]([^'"]+)['"]\s*,\s*self\.([A-Za-z_]\w*)/g

  for (const match of content.matchAll(connectRe)) {
    const widgetName = match[1]
    const signalName = match[2]
    const handler = match[3]
    const element = inferPythonWidgetElement(widgetName, signalName)
    const line = lineNumberFromIndex(content, match.index || 0)
    const id = `symbol:${file}:${line}:ui:${stableHash(`${widgetName}:${signalName}:${handler}`)}`
    if (seen.has(id)) continue
    seen.add(id)
    symbols.push({
      id,
      name: humanizeIdentifier(widgetName).slice(0, 80),
      kind: 'ui_action',
      file_path: file,
      line,
      signature: trimmedSignature(`${element} ${signalName}=self.${handler}`, 220),
      exported: false,
      container: element,
      element,
      handler,
      handler_expression: `self.${handler}`,
    })
  }

  return symbols.slice(0, 60)
}

function extractUiActionsFromJs(file, content) {
  const symbols = []
  const seen = new Set()
  const tagStartRe = /<([A-Z][A-Za-z0-9.]*)\b/g
  for (const match of content.matchAll(tagStartRe)) {
    const start = match.index || 0
    const tag = match[1]
    const end = findJsxOpenTagEnd(content, start)
    if (end < 0 || end - start > 2600) continue
    const rawOpen = content.slice(start, end + 1)
    const attrs = rawOpen.slice(match[0].length, rawOpen.length - 1)
    const handler = jsxAttribute(attrs, ['onPress', 'onClick', 'onSubmit', 'iconPress'])
    const title = jsxAttribute(attrs, ['title', 'label', 'accessibilityLabel', 'aria-label'])
    const hasDirectLabel = Boolean(title)
    const baseName = tag.split('.').pop() || tag
    const isInteractive = Boolean(handler) || /(?:Button|Touchable|Pressable|Action|Item|Card|Atendimento|Comanda|Close)$/i.test(baseName)
    if (!isInteractive || (!handler && !hasDirectLabel)) continue

    const selfClosing = /\/\s*>$/.test(rawOpen)
    let rawBlock = rawOpen
    if (!selfClosing) {
      const closeToken = `</${tag}>`
      const closeIndex = content.indexOf(closeToken, end + 1)
      if (closeIndex > end && closeIndex - start < 9000) {
        rawBlock = content.slice(start, closeIndex + closeToken.length)
      }
    }

    const label = labelFromExpression(title) || textFromJsxChildren(rawBlock) || humanizeComponentName(baseName)
    if (!label || label.length < 2) continue

    const line = lineNumberFromIndex(content, start)
    const id = `symbol:${file}:${line}:ui:${stableHash(`${tag}:${label}:${handler}`)}`
    if (seen.has(id)) continue
    seen.add(id)
    symbols.push({
      id,
      name: label.slice(0, 80),
      kind: 'ui_action',
      file_path: file,
      line,
      signature: trimmedSignature(`${baseName}${handler ? ` onPress=${handler}` : ''}`, 220),
      exported: false,
      container: baseName,
      element: baseName,
      handler: handlerNameFromExpression(handler),
      handler_expression: handler,
    })
  }
  return symbols
}

module.exports = {
  extractUiActionsFromGlade,
  extractUiActionsFromJs,
  extractUiActionsFromPython,
  gladeTitle,
}
