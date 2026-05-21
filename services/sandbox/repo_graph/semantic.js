'use strict'

const fs = require('fs')
const path = require('path')
const { isUiDefinitionFile } = require('./shared')
const { humanizeIdentifier } = require('./text')
const { buildSymbolIndexes, extractFunctionBodyByName, extractSymbolBody, findHandlerSymbols } = require('./symbols')
const {
  cleanSqlTableName, extractFlowTargets, extractPythonFlowTargets, extractReducerActions,
  extractSagaEffects, looksLikeReducerFile, looksLikeSagaFile,
} = require('./flows')
const { collectSemanticInputs } = require('./semantic_inputs')

function makeSemanticNode(id, label, type, pathValue = '', line = 0, detail = '') {
  return { id, label, type, path: pathValue, line, detail }
}

function addSemanticEdge(edges, source, target, type, weight = 1) {
  if (!source || !target || source === target) return
  const id = `sem:${source}->${target}:${type}`
  const existing = edges.get(id)
  if (existing) existing.weight += weight
  else edges.set(id, { id, source, target, type, weight })
}

function extractSemanticGraph(repoPath, codeFiles, uiDefinitionFiles, filesSet, symbolsByFile, allSymbols) {
  const {
    contentByFile, gladeOwnerFiles, gladeTitles, symbolsByFileOut, uiSymbols, uiSymbolsByFile,
  } = collectSemanticInputs(repoPath, codeFiles, uiDefinitionFiles, filesSet)
  const semanticNodes = new Map()
  const semanticEdges = new Map()

  const symbolIndex = buildSymbolIndexes(symbolsByFile, allSymbols)
  const addRouteNode = (route) => {
    const id = `route:${route}`
    if (!semanticNodes.has(id)) semanticNodes.set(id, makeSemanticNode(id, route, 'route', '', 0, 'rota/tela'))
    return id
  }
  const addActionNode = (action) => {
    const id = `action:${action}`
    if (!semanticNodes.has(id)) semanticNodes.set(id, makeSemanticNode(id, action, 'action', '', 0, 'dispatch/action'))
    return id
  }
  const addCallNode = (callName) => {
    const id = `call:${callName}`
    if (!semanticNodes.has(id)) semanticNodes.set(id, makeSemanticNode(id, callName, 'call', '', 0, 'chamada não resolvida'))
    return id
  }
  const addSelectorNode = (selectorName) => {
    const id = `selector:${selectorName}`
    if (!semanticNodes.has(id)) semanticNodes.set(id, makeSemanticNode(id, selectorName, 'call', '', 0, 'redux selector'))
    return id
  }
  const addSagaNode = (file) => {
    const id = `saga:${file}`
    const label = `${path.posix.basename(path.posix.dirname(file)) || path.posix.basename(file)} saga`
    if (!semanticNodes.has(id)) semanticNodes.set(id, makeSemanticNode(id, label, 'saga', file, 0, 'redux saga'))
    return id
  }
  const addReducerNode = (file) => {
    const id = `reducer:${file}`
    const label = `${path.posix.basename(path.posix.dirname(file)) || path.posix.basename(file)} reducer`
    if (!semanticNodes.has(id)) semanticNodes.set(id, makeSemanticNode(id, label, 'reducer', file, 0, 'redux reducer'))
    return id
  }
  const addScreenNode = (file) => {
    const id = `screen:${file}`
    const label = gladeTitles.get(file) || humanizeIdentifier(path.posix.basename(file, path.posix.extname(file)))
    if (!semanticNodes.has(id)) semanticNodes.set(id, makeSemanticNode(id, label, 'route', file, 0, 'tela Glade'))
    return id
  }
  const addDataNode = (table) => {
    const clean = cleanSqlTableName(table)
    const id = `data:${clean}`
    if (!semanticNodes.has(id)) semanticNodes.set(id, makeSemanticNode(id, clean, 'data', '', 0, 'tabela/consulta SQL'))
    return id
  }
  const classSymbolByFileAndName = new Map()
  for (const symbol of allSymbols) {
    if (symbol.kind === 'class') classSymbolByFileAndName.set(`${symbol.file_path}:${symbol.name}`, symbol)
  }
  const addSymbolDefinition = (symbol) => {
    if (!symbol) return
    if (symbol.kind === 'method' && symbol.container) {
      const classSymbol = classSymbolByFileAndName.get(`${symbol.file_path}:${symbol.container}`)
      if (classSymbol) {
        addSemanticEdge(semanticEdges, `file:${symbol.file_path}`, classSymbol.id, 'defines')
        addSemanticEdge(semanticEdges, classSymbol.id, symbol.id, 'defines')
        return
      }
    }
    addSemanticEdge(semanticEdges, `file:${symbol.file_path}`, symbol.id, 'defines')
  }
  const addResolvedCallableEdges = (sourceId, file, callableName, relationType, fallbackNodeFactory = addCallNode) => {
    const targets = findHandlerSymbols(file, callableName, symbolIndex).filter((symbol) => symbol.id !== sourceId)
    if (targets.length) {
      targets.slice(0, 2).forEach((target) => addSemanticEdge(semanticEdges, sourceId, target.id, relationType))
    } else if (callableName) {
      addSemanticEdge(semanticEdges, sourceId, fallbackNodeFactory(callableName), relationType)
    }
  }
  const findUiHandlerSymbols = (ui, handler) => {
    if (!handler) return []
    const all = symbolIndex.byName.get(handler) || []
    const ownerFiles = gladeOwnerFiles.get(ui.file_path) || []
    const ownerMatches = all.filter((symbol) => ownerFiles.includes(symbol.file_path))
    if (ownerMatches.length) return ownerMatches.slice(0, 4)

    const uiDir = path.posix.dirname(ui.file_path)
    const moduleDir = uiDir.endsWith('/glade') ? path.posix.dirname(uiDir) : uiDir
    const localMatches = all.filter((symbol) => path.posix.dirname(symbol.file_path) === moduleDir || path.posix.dirname(symbol.file_path) === uiDir)
    if (localMatches.length) return localMatches.slice(0, 4)

    return findHandlerSymbols(ui.file_path, handler, symbolIndex)
  }
  const findPythonCallSymbols = (file, callName) => {
    if (!callName) return []
    const sameFile = (symbolIndex.byFile.get(file) || []).filter((symbol) => symbol.name === callName)
    if (sameFile.length) return sameFile.slice(0, 3)

    // Em Python legado há muito método genérico ("open", "run", "show").
    // Fora do arquivo atual, só aceitamos nomes com cara de classe/fábrica.
    if (!/^[A-Z]/.test(callName)) return []

    const all = symbolIndex.byName.get(callName) || []
    const currentModule = file.split('/')[0]
    const moduleMatches = all.filter((symbol) => symbol.file_path.split('/')[0] === currentModule)
    if (moduleMatches.length) return moduleMatches.slice(0, 3)
    return all.slice(0, 2)
  }
  const processedPythonSymbols = new Set()
  const addPythonSymbolFlow = (symbol, depth = 0) => {
    if (!symbol || path.posix.extname(symbol.file_path) !== '.py') return
    const key = `${symbol.id}:${depth}`
    if (processedPythonSymbols.has(key) || depth > 1) return
    processedPythonSymbols.add(key)

    let content = contentByFile.get(symbol.file_path) || ''
    if (!content && fs.existsSync(path.join(repoPath, symbol.file_path))) {
      content = fs.readFileSync(path.join(repoPath, symbol.file_path), 'utf8').slice(0, 420_000)
      contentByFile.set(symbol.file_path, content)
    }
    const body = extractSymbolBody(content, symbol)
    if (!body) return

    addSymbolDefinition(symbol)
    const targets = extractPythonFlowTargets(body)
    targets.queries.slice(0, 8).forEach((table) => addSemanticEdge(semanticEdges, symbol.id, addDataNode(table), 'queries'))
    targets.persists.slice(0, 8).forEach((table) => addSemanticEdge(semanticEdges, symbol.id, addDataNode(table), 'persists'))
    targets.calls
      .filter((callName) => callName !== symbol.name)
      .slice(0, 14)
      .forEach((callName) => {
        const callSymbols = findPythonCallSymbols(symbol.file_path, callName).filter((target) => target.id !== symbol.id)
        if (!callSymbols.length) return
        callSymbols.slice(0, 2).forEach((target) => {
          addSymbolDefinition(target)
          addSemanticEdge(semanticEdges, symbol.id, target.id, 'calls')
          addPythonSymbolFlow(target, depth + 1)
        })
      })
  }

  for (const [gladeFile, owners] of gladeOwnerFiles.entries()) {
    const screenNodeId = addScreenNode(gladeFile)
    addSemanticEdge(semanticEdges, `file:${gladeFile}`, screenNodeId, 'defines')
    owners.forEach((ownerFile) => addSemanticEdge(semanticEdges, `file:${ownerFile}`, screenNodeId, 'renders'))
  }

  for (const [file, actions] of uiSymbolsByFile.entries()) {
    if (!isUiDefinitionFile(file)) continue
    const screenNodeId = addScreenNode(file)
    addSemanticEdge(semanticEdges, `file:${file}`, screenNodeId, 'defines')
    actions.forEach((ui) => addSemanticEdge(semanticEdges, screenNodeId, ui.id, 'renders'))
  }

  for (const [file, content] of contentByFile.entries()) {
    if (!looksLikeSagaFile(file, content)) continue
    const fileEffects = extractSagaEffects(content)
    if (fileEffects.watchers.length || fileEffects.forks.length) {
      const sagaNodeId = addSagaNode(file)
      addSemanticEdge(semanticEdges, `file:${file}`, sagaNodeId, 'defines')
      for (const watcher of fileEffects.watchers) {
        const actionNodeId = addActionNode(watcher.action)
        addSemanticEdge(semanticEdges, sagaNodeId, actionNodeId, 'watches')
        if (watcher.worker) addResolvedCallableEdges(actionNodeId, file, watcher.worker, 'triggers')
      }
      fileEffects.forks.forEach((forkName) => addResolvedCallableEdges(sagaNodeId, file, forkName, 'forks'))
    }

    const fileSymbols = (symbolsByFile.get(file) || []).filter((symbol) => ['function', 'method'].includes(symbol.kind))
    for (const symbol of fileSymbols) {
      const body = extractFunctionBodyByName(content, symbol.name)
      if (!body) continue
      const effects = extractSagaEffects(body)
      const hasSagaEffects =
        effects.watchers.length > 0 ||
        effects.puts.length > 0 ||
        effects.calls.length > 0 ||
        effects.selects.length > 0 ||
        effects.forks.length > 0 ||
        /(?:^|[^A-Za-z])(yield|takeLatest|takeEvery|takeLeading|put|call|select|fork)(?:[^A-Za-z]|$)/.test(body)
      if (!hasSagaEffects && !/saga|watch/i.test(symbol.name)) continue

      addSemanticEdge(semanticEdges, `file:${file}`, symbol.id, 'defines')

      for (const watcher of effects.watchers) {
        const actionNodeId = addActionNode(watcher.action)
        addSemanticEdge(semanticEdges, symbol.id, actionNodeId, 'watches')
        if (watcher.worker) addResolvedCallableEdges(actionNodeId, file, watcher.worker, 'triggers')
      }

      effects.puts.forEach((action) => addSemanticEdge(semanticEdges, symbol.id, addActionNode(action), 'dispatches'))
      effects.calls.forEach((callName) => addResolvedCallableEdges(symbol.id, file, callName, 'calls'))
      effects.selects.forEach((selectorName) => addResolvedCallableEdges(symbol.id, file, selectorName, 'selects', addSelectorNode))
      effects.forks.forEach((forkName) => addResolvedCallableEdges(symbol.id, file, forkName, 'forks'))
    }
  }

  for (const [file, content] of contentByFile.entries()) {
    if (!looksLikeReducerFile(file, content)) continue
    const actions = extractReducerActions(content)
    if (!actions.length) continue

    const fileSymbols = (symbolsByFile.get(file) || []).filter((symbol) => ['function', 'method'].includes(symbol.kind))
    const reducerSymbol =
      fileSymbols.find((symbol) => /reducer/i.test(symbol.name)) ||
      fileSymbols.find((symbol) => /action\.type|case\s+/.test(extractFunctionBodyByName(content, symbol.name)))
    const reducerNodeId = reducerSymbol?.id || addReducerNode(file)
    addSemanticEdge(semanticEdges, `file:${file}`, reducerNodeId, 'defines')
    actions.forEach((action) => addSemanticEdge(semanticEdges, addActionNode(action), reducerNodeId, 'reduces'))
  }

  for (const ui of uiSymbols) {
    addSemanticEdge(semanticEdges, `file:${ui.file_path}`, ui.id, 'renders')
    const handlerSymbols = findUiHandlerSymbols(ui, ui.handler)
    if (ui.handler && handlerSymbols.length === 0) {
      addSemanticEdge(semanticEdges, ui.id, addCallNode(ui.handler), 'triggers')
    }
    for (const handlerSymbol of handlerSymbols) {
      addSymbolDefinition(handlerSymbol)
      addSemanticEdge(semanticEdges, ui.id, handlerSymbol.id, 'triggers')
      let handlerContent = contentByFile.get(handlerSymbol.file_path) || ''
      if (!handlerContent && fs.existsSync(path.join(repoPath, handlerSymbol.file_path))) {
        handlerContent = fs.readFileSync(path.join(repoPath, handlerSymbol.file_path), 'utf8').slice(0, 420_000)
      }
      if (handlerContent) contentByFile.set(handlerSymbol.file_path, handlerContent)
      const body = extractSymbolBody(handlerContent, handlerSymbol)
      const targets = path.posix.extname(handlerSymbol.file_path) === '.py' ? extractPythonFlowTargets(body) : extractFlowTargets(body)
      ;(targets.routes || []).forEach((route) => addSemanticEdge(semanticEdges, handlerSymbol.id, addRouteNode(route), 'navigates'))
      ;(targets.actions || []).forEach((action) => addSemanticEdge(semanticEdges, handlerSymbol.id, addActionNode(action), 'dispatches'))
      ;(targets.queries || []).slice(0, 8).forEach((table) => addSemanticEdge(semanticEdges, handlerSymbol.id, addDataNode(table), 'queries'))
      ;(targets.persists || []).slice(0, 8).forEach((table) => addSemanticEdge(semanticEdges, handlerSymbol.id, addDataNode(table), 'persists'))
      targets.calls
        .filter((callName) => callName !== handlerSymbol.name)
        .slice(0, 8)
        .forEach((callName) => {
          const isPythonHandler = path.posix.extname(handlerSymbol.file_path) === '.py'
          const callSymbols = isPythonHandler
            ? findPythonCallSymbols(handlerSymbol.file_path, callName)
            : findHandlerSymbols(handlerSymbol.file_path, callName, symbolIndex)
          if (callSymbols.length) {
            callSymbols.slice(0, 2).forEach((callSymbol) => {
              addSymbolDefinition(callSymbol)
              addSemanticEdge(semanticEdges, handlerSymbol.id, callSymbol.id, 'calls')
              addPythonSymbolFlow(callSymbol, 1)
            })
          } else if (!isPythonHandler) {
            addSemanticEdge(semanticEdges, handlerSymbol.id, addCallNode(callName), 'calls')
          }
        })
      addPythonSymbolFlow(handlerSymbol)
    }

    const inlineTargets = extractFlowTargets(`${ui.handler_expression || ''}\n${ui.signature}`)
    inlineTargets.routes.forEach((route) => addSemanticEdge(semanticEdges, ui.id, addRouteNode(route), 'navigates'))
    inlineTargets.actions.forEach((action) => addSemanticEdge(semanticEdges, ui.id, addActionNode(action), 'dispatches'))
    inlineTargets.calls
      .filter((callName) => callName !== ui.handler)
      .slice(0, 6)
      .forEach((callName) => {
        const callSymbols = findHandlerSymbols(ui.file_path, callName, symbolIndex)
        if (callSymbols.length) {
          callSymbols.slice(0, 2).forEach((callSymbol) => addSemanticEdge(semanticEdges, ui.id, callSymbol.id, 'calls'))
        } else {
          addSemanticEdge(semanticEdges, ui.id, addCallNode(callName), 'calls')
        }
      })
  }

  return {
    symbolsByFile: symbolsByFileOut,
    uiSymbols,
    semanticNodes: Array.from(semanticNodes.values()),
    semanticEdges: Array.from(semanticEdges.values()).sort((a, b) => a.type.localeCompare(b.type) || a.id.localeCompare(b.id)),
  }
}

module.exports = { addSemanticEdge, extractSemanticGraph, makeSemanticNode }
