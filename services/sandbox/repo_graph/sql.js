'use strict'

const fs = require('fs/promises')
const os = require('os')
const path = require('path')
const { execFile } = require('child_process')
const { promisify } = require('util')

const execFileAsync = promisify(execFile)
const SQL_SOURCE = 'static_sql'
const SQL_VERSION = '0.1.0'

function isSqlFile(file) {
  return path.posix.extname(file).toLowerCase() === '.sql'
}

function normalizeNode(node) {
  const version = node.extractor_version || SQL_VERSION
  const source = node.source_extractor || SQL_SOURCE
  return {
    ...node,
    id: String(node.id || ''),
    label: String(node.label || node.name || node.id || ''),
    type: String(node.type || node.kind || 'sql_entity'),
    path: String(node.path || node.file_path || ''),
    line: Number(node.line || node.line_start || 0),
    detail: String(node.detail || ''),
    source_extractor: source,
    extractor_version: version,
  }
}

function normalizeEdge(edge) {
  const version = edge.extractor_version || SQL_VERSION
  const source = edge.source_extractor || SQL_SOURCE
  const targetExternal = edge.target_external ? String(edge.target_external) : null
  const target = edge.target ? String(edge.target) : targetExternal
  return {
    ...edge,
    id: String(edge.id || `sql:${edge.source}->${target}:${edge.type || 'related'}`),
    source: String(edge.source || ''),
    target,
    target_external: targetExternal || undefined,
    type: String(edge.type || 'related'),
    weight: Number(edge.weight || 1),
    source_extractor: source,
    extractor_version: version,
  }
}

function diagnosticToFinding(diagnostic, index) {
  const level = diagnostic.level === 'error' ? 'error' : 'warning'
  const severity = level === 'error' ? 'medium' : 'low'
  const file = String(diagnostic.file || '')
  const line = Number(diagnostic.line || 0)
  return {
    id: `sql:${index}:${file}:${line}`,
    type: 'sql_diagnostic',
    severity,
    level,
    source: 'sql',
    title: `SQL ${level}: ${file || 'workspace'}`,
    detail: String(diagnostic.message || ''),
    node_id: '',
    path: file,
  }
}

async function extractSqlGraph(repoPath, files) {
  const sqlFiles = files.filter(isSqlFile)
  if (sqlFiles.length === 0) {
    return { nodes: [], edges: [], findings: [] }
  }

  const command = process.env.CAPPY_SQL_EXTRACTOR || 'cappy-sql-extractor'
  const timeoutMs = Number(process.env.CAPPY_SQL_TIMEOUT_MS || 40000)
  const outPath = path.join(os.tmpdir(), `cappy-sql-${process.pid}-${Date.now()}.json`)
  const args = ['--repo', repoPath, '--out', outPath, '--paths', sqlFiles.join(',')]
  try {
    await execFileAsync(command, args, {
      timeout: Number.isFinite(timeoutMs) && timeoutMs > 0 ? timeoutMs : 40000,
      maxBuffer: 20 * 1024 * 1024,
    })
    const raw = await fs.readFile(outPath, 'utf8')
    const output = JSON.parse(raw)
    return {
      nodes: (output.nodes || []).map(normalizeNode).filter((node) => node.id),
      edges: (output.edges || []).map(normalizeEdge).filter((edge) => edge.source && edge.target),
      findings: (output.diagnostics || []).map(diagnosticToFinding),
      timings_ms: output.timings_ms || {},
    }
  } catch (err) {
    return {
      nodes: [],
      edges: [],
      findings: [{
        id: 'sql:extractor-error',
        type: 'sql_diagnostic',
        severity: 'medium',
        level: 'error',
        source: 'sql',
        title: 'SQL extractor failed',
        detail: err.message || String(err),
        node_id: '',
        path: '',
      }],
    }
  } finally {
    await fs.rm(outPath, { force: true }).catch(() => {})
  }
}

module.exports = { extractSqlGraph, SQL_SOURCE, SQL_VERSION }
