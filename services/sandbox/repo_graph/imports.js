'use strict'

const fs = require('fs')
const path = require('path')
const { execFileSync } = require('child_process')
const {
  JS_IMPORT_RE,
  PY_FROM_RE,
  PY_IMPORT_RE,
  RESOLVE_EXTENSIONS,
  isUiDefinitionFile,
  moduleForFile,
} = require('./shared')

function resolveCandidate(base, filesSet) {
  const clean = base.replace(/\\/g, '/').replace(/^\/+/, '')
  const candidates = []
  for (const ext of RESOLVE_EXTENSIONS) candidates.push(`${clean}${ext}`)
  for (const ext of RESOLVE_EXTENSIONS.slice(1)) candidates.push(`${clean}/index${ext}`)
  return candidates.find((candidate) => filesSet.has(candidate)) || ''
}

function resolveJsImport(file, spec, filesSet) {
  if (!spec.startsWith('.')) return ''
  const base = path.posix.normalize(path.posix.join(path.posix.dirname(file), spec))
  if (base.startsWith('../')) return ''
  return resolveCandidate(base, filesSet)
}

function resolvePyImport(file, spec, filesSet) {
  const currentDir = path.posix.dirname(file)
  if (spec.startsWith('.')) {
    const dots = spec.match(/^\.+/)?.[0].length || 0
    const rest = spec.slice(dots).replace(/\./g, '/')
    let dir = currentDir
    for (let i = 1; i < dots; i += 1) dir = path.posix.dirname(dir)
    return resolveCandidate(path.posix.normalize(path.posix.join(dir, rest)), filesSet)
  }
  const modulePath = spec.replace(/\./g, '/')
  const workspace = moduleForFile(file)
  const scoped = workspace === 'root' ? modulePath : `${workspace}/${modulePath}`
  return resolveCandidate(scoped, filesSet) || resolveCandidate(modulePath, filesSet)
}

function resolveUiDefinitionPath(file, spec, filesSet) {
  const clean = spec.replace(/\\/g, '/').replace(/^\/+/, '').replace(/\.(?:glade|ui)$/i, '')
  if (!clean || /^https?:\/\//i.test(clean)) return ''
  if (spec.startsWith('.')) {
    const base = path.posix.normalize(path.posix.join(path.posix.dirname(file), clean))
    if (base.startsWith('../')) return ''
    return resolveCandidate(base, filesSet)
  }
  return resolveCandidate(clean, filesSet)
}

function extractUiDefinitionLinksFromPython(file, content, filesSet) {
  const links = new Set()
  const add = (raw) => {
    const resolved = resolveUiDefinitionPath(file, raw, filesSet)
    if (resolved && isUiDefinitionFile(resolved)) links.add(resolved)
  }

  for (const match of content.matchAll(/\binitialize\s*\(\s*['"]([^'"]+)['"]/g)) add(match[1])
  for (const match of content.matchAll(/\b(?:gtk\.glade\.XML|add_from_file|add_objects_from_file)\s*\(\s*['"]([^'"]+)['"]/g)) add(match[1])
  for (const match of content.matchAll(/['"]([^'"]+\.glade)['"]/g)) add(match[1])

  return Array.from(links).sort()
}

function importSpecs(file, content) {
  const ext = path.posix.extname(file)
  const specs = []
  if (['.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs'].includes(ext)) {
    for (const match of content.matchAll(JS_IMPORT_RE)) specs.push(match[1] || match[2] || match[3] || '')
  }
  if (ext === '.py') {
    for (const match of content.matchAll(PY_FROM_RE)) specs.push(match[1] || '')
    for (const match of content.matchAll(PY_IMPORT_RE)) specs.push(match[1] || '')
  }
  return specs.filter(Boolean)
}

function addEdge(edges, source, target) {
  if (!source || !target || source === target) return
  const id = `${source}->${target}`
  const existing = edges.get(id)
  if (existing) existing.weight += 1
  else edges.set(id, { id, source, target, type: 'imports', weight: 1 })
}

function readTrackedFiles(repoPath, maxFiles) {
  const output = execFileSync('git', ['-C', repoPath, 'ls-files'], {
    encoding: 'utf8',
    timeout: 30_000,
    maxBuffer: 20 * 1024 * 1024,
  })
  return output.split(/\r?\n/).filter(Boolean).slice(0, maxFiles)
}

function buildModules(files) {
  const modules = new Map()
  for (const file of files) {
    const modulePath = moduleForFile(file)
    const module = modules.get(modulePath) || {
      id: `module:${modulePath}`,
      label: modulePath,
      type: 'module',
      path: modulePath,
      file_count: 0,
      import_count: 0,
      imported_by_count: 0,
      isolated: false,
    }
    module.file_count += 1
    modules.set(modulePath, module)
  }
  return modules
}

function buildFileImports(repoPath, codeFiles, filesSet) {
  const importsByFile = new Map()
  const importedByFile = new Map()
  const moduleEdges = new Map()
  const fileEdges = new Map()

  for (const file of codeFiles) {
    importsByFile.set(file, [])
    importedByFile.set(file, [])
  }

  for (const file of codeFiles) {
    let content = ''
    try {
      content = fs.readFileSync(path.join(repoPath, file), 'utf8').slice(0, 240_000)
    } catch {
      continue
    }
    for (const spec of importSpecs(file, content)) {
      const targetFile = path.posix.extname(file) === '.py'
        ? resolvePyImport(file, spec, filesSet)
        : resolveJsImport(file, spec, filesSet)
      if (!targetFile || targetFile === file) continue

      importsByFile.get(file)?.push(targetFile)
      importedByFile.get(targetFile)?.push(file)
      addEdge(moduleEdges, `module:${moduleForFile(file)}`, `module:${moduleForFile(targetFile)}`)
      addEdge(fileEdges, `file:${file}`, `file:${targetFile}`)
    }
  }

  const uniqueSortedMap = (input) => {
    const out = new Map()
    for (const [key, values] of input.entries()) {
      out.set(key, Array.from(new Set(values)).sort())
    }
    return out
  }

  return {
    importsByFile: uniqueSortedMap(importsByFile),
    importedByFile: uniqueSortedMap(importedByFile),
    moduleEdges: Array.from(moduleEdges.values()).sort((a, b) => b.weight - a.weight),
    fileEdges: Array.from(fileEdges.values()).sort((a, b) => b.weight - a.weight),
  }
}

module.exports = {
  buildFileImports,
  buildModules,
  extractUiDefinitionLinksFromPython,
  importSpecs,
  readTrackedFiles,
  resolveCandidate,
  resolveJsImport,
  resolvePyImport,
  resolveUiDefinitionPath,
}
