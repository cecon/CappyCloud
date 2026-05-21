'use strict'

const fs = require('fs')
const path = require('path')
const { extractUiDefinitionLinksFromPython } = require('./imports')
const {
  extractUiActionsFromGlade,
  extractUiActionsFromJs,
  extractUiActionsFromPython,
  gladeTitle,
} = require('./ui_extractors')

function collectSemanticInputs(repoPath, codeFiles, uiDefinitionFiles, filesSet) {
  const symbolsByFileOut = new Map()
  const uiSymbols = []
  const uiSymbolsByFile = new Map()
  const contentByFile = new Map()
  const gladeOwnerFiles = new Map()
  const gladeTitles = new Map()
  const maxUiSymbols = 1200

  const appendUiSymbols = (file, actions) => {
    if (!actions.length || uiSymbols.length >= maxUiSymbols) return
    const selected = actions.slice(0, maxUiSymbols - uiSymbols.length)
    symbolsByFileOut.set(file, [...(symbolsByFileOut.get(file) || []), ...selected])
    uiSymbolsByFile.set(file, [...(uiSymbolsByFile.get(file) || []), ...selected])
    uiSymbols.push(...selected)
  }

  for (const file of codeFiles) {
    let content = ''
    try {
      content = fs.readFileSync(path.join(repoPath, file), 'utf8').slice(0, 420_000)
    } catch {
      continue
    }
    const ext = path.posix.extname(file)
    contentByFile.set(file, content)
    if (['.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs'].includes(ext)) {
      appendUiSymbols(file, extractUiActionsFromJs(file, content))
    }
    if (ext === '.py') {
      appendUiSymbols(file, extractUiActionsFromPython(file, content))
      for (const gladeFile of extractUiDefinitionLinksFromPython(file, content, filesSet)) {
        const owners = gladeOwnerFiles.get(gladeFile) || []
        owners.push(file)
        gladeOwnerFiles.set(gladeFile, Array.from(new Set(owners)).sort())
      }
    }
  }

  for (const file of uiDefinitionFiles) {
    let content = ''
    try {
      content = fs.readFileSync(path.join(repoPath, file), 'utf8').slice(0, 420_000)
    } catch {
      continue
    }
    contentByFile.set(file, content)
    gladeTitles.set(file, gladeTitle(content, file))
    appendUiSymbols(file, extractUiActionsFromGlade(file, content))
  }

  return { contentByFile, gladeOwnerFiles, gladeTitles, symbolsByFileOut, uiSymbols, uiSymbolsByFile }
}

module.exports = { collectSemanticInputs }
