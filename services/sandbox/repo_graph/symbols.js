'use strict'

const fs = require('fs')
const path = require('path')
const {
  escapeRegExp,
  lineNumberFromIndex,
  readBalancedExpression,
  trimmedSignature,
} = require('./text')

function extractJsSymbols(file, content) {
  const symbols = []
  const seen = new Set()
  const add = (kind, name, index, signature, exported = false, container = '') => {
    if (!name || ['if', 'for', 'while', 'switch', 'catch', 'return'].includes(name)) return
    const line = lineNumberFromIndex(content, index)
    const id = `symbol:${file}:${line}:${name}`
    if (seen.has(id)) return
    seen.add(id)
    symbols.push({
      id,
      name,
      kind,
      file_path: file,
      line,
      signature: trimmedSignature(signature || name),
      exported,
      container,
    })
  }

  const patterns = [
    { kind: 'function', re: /\bexport\s+default\s+(?:async\s+)?function\s*\*?\s+([A-Za-z_$][\w$]*)\s*\([^)]*\)/g, name: 1, exported: 0 },
    { kind: 'function', re: /\b(export\s+)?(?:async\s+)?function\s*\*?\s+([A-Za-z_$][\w$]*)\s*\([^)]*\)/g, name: 2, exported: 1 },
    { kind: 'function', re: /\b(export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>/g, name: 2, exported: 1 },
    { kind: 'function', re: /\b(export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s+)?function\s*\*?\b/g, name: 2, exported: 1 },
    { kind: 'class', re: /\b(export\s+)?class\s+([A-Za-z_$][\w$]*)\b/g, name: 2, exported: 1 },
  ]
  for (const pattern of patterns) {
    for (const match of content.matchAll(pattern.re)) {
      add(pattern.kind, match[pattern.name], match.index || 0, match[0], Boolean(match[pattern.exported]))
    }
  }

  const lines = content.split(/\r?\n/)
  let currentClass = ''
  let classIndent = -1
  lines.forEach((line, index) => {
    const classMatch = line.match(/^(\s*)(?:export\s+)?class\s+([A-Za-z_$][\w$]*)\b/)
    if (classMatch) {
      currentClass = classMatch[2]
      classIndent = classMatch[1].length
      return
    }
    const indent = line.match(/^\s*/)?.[0].length || 0
    if (currentClass && line.trim() && indent <= classIndent && !line.trim().startsWith('//')) {
      currentClass = ''
      classIndent = -1
    }
    if (!currentClass) return
    const methodMatch = line.match(/^\s*(?:async\s+)?([A-Za-z_$][\w$]*)\s*\([^)]*\)\s*\{?/)
    if (methodMatch && !['constructor', 'if', 'for', 'while', 'switch'].includes(methodMatch[1])) {
      add('method', methodMatch[1], content.indexOf(line), line, false, currentClass)
      return
    }
    const propertyMethodMatch = line.match(/^\s*(?:async\s+)?([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?(?:\([^)]*\)|[A-Za-z_$][\w$]*)\s*=>/)
    if (propertyMethodMatch && !['constructor', 'if', 'for', 'while', 'switch'].includes(propertyMethodMatch[1])) {
      add('method', propertyMethodMatch[1], content.indexOf(line), line, false, currentClass)
    }
  })

  return symbols
}

function extractPySymbols(file, content) {
  const symbols = []
  const add = (kind, name, index, signature, container = '') => {
    const line = lineNumberFromIndex(content, index)
    symbols.push({
      id: `symbol:${file}:${line}:${name}`,
      name,
      kind,
      file_path: file,
      line,
      signature: trimmedSignature(signature || name),
      exported: !name.startsWith('_'),
      container,
    })
  }

  const lines = content.split(/\r?\n/)
  let currentClass = ''
  let classIndent = -1
  let offset = 0
  for (const line of lines) {
    const classMatch = line.match(/^(\s*)class\s+([A-Za-z_]\w*)\b/)
    if (classMatch) {
      currentClass = classMatch[2]
      classIndent = classMatch[1].length
      add('class', currentClass, offset, line)
    } else {
      const indent = line.match(/^\s*/)?.[0].length || 0
      if (currentClass && line.trim() && indent <= classIndent && !line.trim().startsWith('#')) {
        currentClass = ''
        classIndent = -1
      }
      const defMatch = line.match(/^(\s*)(?:async\s+)?def\s+([A-Za-z_]\w*)\s*\([^)]*\)/)
      if (defMatch) {
        const kind = currentClass && defMatch[1].length > classIndent ? 'method' : 'function'
        add(kind, defMatch[2], offset, line, kind === 'method' ? currentClass : '')
      }
    }
    offset += line.length + 1
  }
  return symbols
}

function extractSymbols(repoPath, codeFiles) {
  const symbolsByFile = new Map()
  const allSymbols = []
  for (const file of codeFiles) {
    let content = ''
    try {
      content = fs.readFileSync(path.join(repoPath, file), 'utf8').slice(0, 320_000)
    } catch {
      symbolsByFile.set(file, [])
      continue
    }
    const ext = path.posix.extname(file)
    const symbols = ext === '.py' ? extractPySymbols(file, content) : extractJsSymbols(file, content)
    symbolsByFile.set(file, symbols)
    allSymbols.push(...symbols)
  }
  return { symbolsByFile, allSymbols }
}

function extractReferenceSymbols(repoPath, referenceFiles) {
  const symbolsByFile = new Map()
  const allSymbols = []
  for (const file of referenceFiles) {
    let content = ''
    try {
      content = fs.readFileSync(path.join(repoPath, file), 'utf8').slice(0, 160_000)
    } catch {
      symbolsByFile.set(file, [])
      continue
    }
    const symbols = []
    if (path.posix.basename(file) === '.gitignore') {
      const lines = content.split(/\r?\n/)
      lines.forEach((line, index) => {
        const pattern = line.trim()
        if (!pattern || pattern.startsWith('#')) return
        symbols.push({
          id: `symbol:${file}:${index + 1}:ignore:${pattern}`,
          name: pattern,
          kind: 'ignore',
          file_path: file,
          line: index + 1,
          signature: `ignora ${pattern}`,
          exported: false,
          container: '.gitignore',
        })
      })
    }
    symbolsByFile.set(file, symbols)
    allSymbols.push(...symbols)
  }
  return { symbolsByFile, allSymbols }
}

function extractFunctionBodyByName(content, name) {
  if (!name) return ''
  const escaped = escapeRegExp(name)
  const patterns = [
    new RegExp(`\\b${escaped}\\s*=\\s*(?:async\\s*)?\\([^)]*\\)\\s*=>\\s*\\{`, 'm'),
    new RegExp(`\\b${escaped}\\s*=\\s*(?:async\\s*)?function\\s*\\([^)]*\\)\\s*\\{`, 'm'),
    new RegExp(`\\b(?:async\\s+)?function\\s+${escaped}\\s*\\([^)]*\\)\\s*\\{`, 'm'),
    new RegExp(`\\b(?:async\\s+)?${escaped}\\s*\\([^)]*\\)\\s*\\{`, 'm'),
  ]
  for (const pattern of patterns) {
    const match = pattern.exec(content)
    if (!match) continue
    const brace = content.indexOf('{', (match.index || 0) + match[0].length - 1)
    if (brace < 0) continue
    return readBalancedExpression(content, brace).slice(0, 24_000)
  }

  const arrow = new RegExp(`\\b${escaped}\\s*=\\s*(?:async\\s*)?\\([^)]*\\)\\s*=>\\s*([^;\\n]+)`, 'm').exec(content)
  return arrow?.[1]?.slice(0, 4000) || ''
}

function extractPyBlockByLine(content, lineNumber) {
  if (!lineNumber || lineNumber < 1) return ''
  const lines = content.split(/\r?\n/)
  const start = lineNumber - 1
  const firstLine = lines[start] || ''
  const baseIndent = firstLine.match(/^\s*/)?.[0].length || 0
  const body = [firstLine]

  for (let index = start + 1; index < lines.length; index += 1) {
    const line = lines[index]
    const trimmed = line.trim()
    const indent = line.match(/^\s*/)?.[0].length || 0
    if (trimmed && indent <= baseIndent && !trimmed.startsWith('#')) break
    body.push(line)
    if (body.join('\n').length > 24_000) break
  }

  return body.join('\n')
}

function extractSymbolBody(content, symbol) {
  if (!symbol) return ''
  if (path.posix.extname(symbol.file_path) === '.py') return extractPyBlockByLine(content, symbol.line)
  return extractFunctionBodyByName(content, symbol.name)
}

function buildSymbolIndexes(symbolsByFile, allSymbols) {
  const byName = new Map()
  for (const symbol of allSymbols) {
    if (symbol.kind === 'ui_action' || symbol.kind === 'ignore') continue
    const list = byName.get(symbol.name) || []
    list.push(symbol)
    byName.set(symbol.name, list)
  }
  for (const list of byName.values()) {
    list.sort((a, b) => a.file_path.localeCompare(b.file_path) || a.line - b.line)
  }
  return {
    byName,
    byFile: symbolsByFile,
  }
}

function findHandlerSymbols(file, handler, symbolIndex) {
  if (!handler) return []
  const sameFile = (symbolIndex.byFile.get(file) || []).filter((symbol) => symbol.name === handler)
  if (sameFile.length) return sameFile.slice(0, 3)

  const sameDir = path.posix.dirname(file)
  const all = symbolIndex.byName.get(handler) || []
  const local = all.filter((symbol) => path.posix.dirname(symbol.file_path) === sameDir)
  if (local.length) return local.slice(0, 3)

  const containerFile = path.posix.join(sameDir, 'container.js')
  const container = all.filter((symbol) => symbol.file_path === containerFile)
  if (container.length) return container.slice(0, 3)

  return all.slice(0, 2)
}

module.exports = {
  buildSymbolIndexes,
  extractFunctionBodyByName,
  extractJsSymbols,
  extractPyBlockByLine,
  extractPySymbols,
  extractReferenceSymbols,
  extractSymbolBody,
  extractSymbols,
  findHandlerSymbols,
}
