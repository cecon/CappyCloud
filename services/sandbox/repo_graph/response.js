'use strict'

const fs = require('fs')
const path = require('path')
const {
  isCodeFile,
  isReferenceFile,
  isUiDefinitionFile,
  labelForFile,
  moduleForFile,
  safeRepoPath,
} = require('./shared')
const { buildFileImports, buildModules, readTrackedFiles } = require('./imports')
const { extractReferenceSymbols, extractSymbols } = require('./symbols')
const { extractSemanticGraph } = require('./semantic')

function mergeSymbolMaps(primary, secondary) {
  const merged = new Map(primary)
  for (const [file, symbols] of secondary.entries()) {
    merged.set(file, [...(merged.get(file) || []), ...symbols])
  }
  return merged
}

function referenceTargets(symbolsByFile) {
  const refs = new Map()
  for (const [file, symbols] of symbolsByFile.entries()) {
    if (path.posix.basename(file) === '.gitignore') {
      refs.set(file, symbols.map((symbol) => `ignore:${symbol.name}`))
    }
  }
  return refs
}

function sourceLineCount(repoPath, file) {
  try {
    return fs.readFileSync(path.join(repoPath, file), 'utf8').split(/\r?\n/).length
  } catch {
    return 0
  }
}

function looksLikeEntrypoint(file) {
  const base = path.posix.basename(file).toLowerCase()
  return [
    'index.js',
    'index.jsx',
    'index.ts',
    'index.tsx',
    'main.js',
    'main.jsx',
    'main.ts',
    'main.tsx',
    'app.js',
    'app.jsx',
    'app.ts',
    'app.tsx',
    '__init__.py',
    'manage.py',
  ].includes(base)
}

function looksLikeTest(file) {
  return /(^|\/)(__tests__|test|tests|spec)\//i.test(file) || /\.(test|spec)\.[jt]sx?$/i.test(file) || /test_.*\.py$/i.test(path.posix.basename(file))
}

function buildFileRows(repoPath, graphFiles, importsByFile, importedByFile, symbolsByFile, refsByFile) {
  return graphFiles.map((file) => {
    const imports = [...(importsByFile.get(file) || []), ...(refsByFile.get(file) || [])]
    const importedBy = importedByFile.get(file) || []
    const symbols = symbolsByFile.get(file) || []
    const entrypoint = looksLikeEntrypoint(file)
    const isolated = imports.length === 0 && importedBy.length === 0
    const unreferenced = importedBy.length === 0 && !entrypoint && !looksLikeTest(file)
    return {
      id: `file:${file}`,
      path: file,
      label: labelForFile(file),
      module: moduleForFile(file),
      extension: path.posix.extname(file).replace('.', ''),
      line_count: sourceLineCount(repoPath, file),
      symbol_count: symbols.length,
      imports,
      imported_by: importedBy,
      import_count: imports.length,
      imported_by_count: importedBy.length,
      isolated,
      entrypoint,
      unreferenced,
      symbols: symbols.map((symbol) => symbol.id),
    }
  })
}

function fileFindings(fileRows) {
  return fileRows
    .filter((file) => file.unreferenced || file.isolated)
    .slice(0, 80)
    .map((file) => ({
      id: `file-signal:${file.path}`,
      type: file.isolated ? 'isolated_file' : 'unreferenced_file',
      severity: file.entrypoint ? 'low' : 'medium',
      title: `${file.path} sem referência local detectada`,
      detail: file.isolated
        ? 'Nenhum import local entrou ou saiu deste arquivo neste corte.'
        : 'O arquivo não aparece como alvo de import local; pode ser entrypoint dinâmico, config ou código órfão.',
      node_id: file.id,
      path: file.path,
    }))
}

function referenceFileEdges(refsByFile) {
  const edges = []
  for (const [file, refs] of refsByFile.entries()) {
    for (const ref of refs) {
      edges.push({
        id: `file:${file}->${ref}`,
        source: `file:${file}`,
        target: ref,
        type: ref.startsWith('ignore:') ? 'ignores' : 'references',
        weight: 1,
      })
    }
  }
  return edges
}

function selectResponseSymbols(allSymbols, semanticEdges, limit = 3000) {
  const referenced = new Set()
  for (const edge of semanticEdges) {
    if (edge.source?.startsWith('symbol:')) referenced.add(edge.source)
    if (edge.target?.startsWith('symbol:')) referenced.add(edge.target)
  }
  return allSymbols
    .sort((a, b) => {
      const priority = Number(!referenced.has(a.id)) - Number(!referenced.has(b.id))
      if (priority !== 0) return priority
      return a.file_path.localeCompare(b.file_path) || a.line - b.line || a.name.localeCompare(b.name)
    })
    .slice(0, limit)
}

function markNodeConnectivity(nodes, edgeRows) {
  const incoming = new Map()
  const outgoing = new Map()
  for (const edge of edgeRows) {
    outgoing.set(edge.source, (outgoing.get(edge.source) || 0) + edge.weight)
    incoming.set(edge.target, (incoming.get(edge.target) || 0) + edge.weight)
  }
  for (const node of nodes) {
    if (node.type !== 'module') continue
    node.import_count = outgoing.get(node.id) || 0
    node.imported_by_count = incoming.get(node.id) || 0
    node.isolated = node.import_count === 0 && node.imported_by_count === 0
  }
}

function isolatedFindings(nodes) {
  return nodes
    .filter((node) => node.type === 'module' && node.isolated)
    .map((node) => ({
      id: `isolated:${node.path}`,
      type: 'isolated_module',
      severity: node.path === 'docs' ? 'low' : 'medium',
      title: `${node.label} sem ligações detectadas`,
      detail: 'Nenhum import local entrou ou saiu deste módulo na análise leve.',
      node_id: node.id,
      path: node.path,
    }))
}

function graphForRepo(slug, query) {
  const repoPath = safeRepoPath(slug)
  const maxFiles = Math.max(50, Math.min(Number(query.get('max_files') || 1200), 5000))
  const files = readTrackedFiles(repoPath, maxFiles)
  const filesSet = new Set(files)
  const codeFiles = files.filter(isCodeFile)
  const uiDefinitionFiles = files.filter(isUiDefinitionFile)
  const referenceFiles = files.filter((file) => isReferenceFile(file) && !codeFiles.includes(file) && !uiDefinitionFiles.includes(file))
  const graphFiles = [...codeFiles, ...uiDefinitionFiles, ...referenceFiles]
  const modules = buildModules(graphFiles)
  const importGraph = buildFileImports(repoPath, codeFiles, filesSet)
  const codeSymbols = extractSymbols(repoPath, codeFiles)
  const referenceSymbols = extractReferenceSymbols(repoPath, referenceFiles)
  const baseSymbolsByFile = mergeSymbolMaps(codeSymbols.symbolsByFile, referenceSymbols.symbolsByFile)
  const baseSymbols = [...codeSymbols.allSymbols, ...referenceSymbols.allSymbols]
  const semanticGraph = extractSemanticGraph(repoPath, codeFiles, uiDefinitionFiles, filesSet, baseSymbolsByFile, baseSymbols)
  const symbolsByFile = mergeSymbolMaps(baseSymbolsByFile, semanticGraph.symbolsByFile)
  const allSymbols = [...baseSymbols, ...semanticGraph.uiSymbols]
  const refsByFile = referenceTargets(referenceSymbols.symbolsByFile)
  const fileRows = buildFileRows(
    repoPath,
    graphFiles,
    importGraph.importsByFile,
    importGraph.importedByFile,
    symbolsByFile,
    refsByFile,
  )
  const edgeRows = importGraph.moduleEdges
  const nodes = [
    { id: `repo:${slug}`, label: slug, type: 'repo', path: repoPath, file_count: files.length },
    ...Array.from(modules.values()).sort((a, b) => a.label.localeCompare(b.label)),
  ]
  markNodeConnectivity(nodes, edgeRows)
  const findings = fileFindings(fileRows)
  const isolatedFiles = fileRows.filter((file) => file.isolated).length
  const entrypoints = fileRows.filter((file) => file.entrypoint).length
  const unreferencedFiles = fileRows.filter((file) => file.unreferenced).length
  return {
    slug,
    repo_path: repoPath,
    generated_at: new Date().toISOString(),
    stats: {
      files: files.length,
      code_files: graphFiles.length,
      modules: modules.size,
      links: importGraph.fileEdges.length,
      isolated: isolatedFiles,
      symbols: allSymbols.length,
      entrypoints,
      unreferenced_files: unreferencedFiles,
      ui_actions: semanticGraph.uiSymbols.length,
      flows: semanticGraph.semanticEdges.length,
    },
    nodes,
    edges: [
      ...nodes
        .filter((node) => node.type === 'module')
        .map((node) => ({
          id: `contains:${slug}:${node.id}`,
          source: `repo:${slug}`,
          target: node.id,
          type: 'contains',
          weight: Math.max(1, node.file_count),
        })),
      ...edgeRows,
    ],
    files: fileRows.sort((a, b) => a.path.localeCompare(b.path)),
    symbols: selectResponseSymbols(allSymbols, semanticGraph.semanticEdges),
    file_edges: [...importGraph.fileEdges, ...referenceFileEdges(refsByFile)],
    semantic_nodes: semanticGraph.semanticNodes,
    semantic_edges: semanticGraph.semanticEdges,
    findings,
  }
}

module.exports = { graphForRepo }
