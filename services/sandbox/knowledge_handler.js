'use strict'
// Conhecimento do workspace: grafo de código do graphify (AST, sem LLM).
//
//   POST /workspaces/:slug/knowledge/build   → inicia a reconstrução (202; uma por vez)
//   GET  /workspaces/:slug/knowledge         → status + arquivos de knowledge/ e memory/
//   GET  /workspaces/:slug/knowledge/file?path=knowledge/...   → conteúdo (texto, limitado)
//
// Para cada repositório do workspace (links em repos/), com a trava do clone:
// traz o clone para a última versão do remoto (só fast-forward), roda
// `graphify update` (saída em <clone>/graphify-out, fora do git) e copia o
// relatório. Depois junta os grafos em knowledge/graphify/graph.json, que o
// agente consulta com `graphify query --graph`.

const fs = require('fs')
const path = require('path').posix
const { execFile } = require('child_process')
const { promisify } = require('util')

const run = promisify(execFile)
const GRAPHIFY = process.env.GRAPHIFY_BIN || 'graphify'
const WORKSPACE_SLUG = /^[a-z0-9][a-z0-9-]{1,62}$/
const BROWSABLE = ['knowledge', 'memory']
const MAX_FILE_BYTES = 200_000
const MAX_LIST = 500
const building = new Map()

function workspaceRoot(slug, reposRoot = '/repos') {
  if (!WORKSPACE_SLUG.test(String(slug || ''))) throw new Error(`workspace slug inválido: ${slug}`)
  return path.join(reposRoot, 'workspaces', slug)
}

function graphDir(root) {
  return path.join(root, 'knowledge', 'graphify')
}

function readStatus(root) {
  try {
    return JSON.parse(fs.readFileSync(path.join(graphDir(root), 'status.json'), 'utf8'))
  } catch {
    return { state: 'never_built' }
  }
}

function writeStatus(root, status) {
  fs.mkdirSync(graphDir(root), { recursive: true })
  fs.writeFileSync(path.join(graphDir(root), 'status.json'), JSON.stringify(status, null, 2))
}

/** Números da linha "Rebuilt: 400 nodes, 715 edges, 22 communities". */
function parseRebuilt(output) {
  const match = String(output || '').match(/(\d+) nodes, (\d+) edges(?:, (\d+) communities)?/)
  return match ? { nodes: Number(match[1]), edges: Number(match[2]), communities: Number(match[3] || 0) } : {}
}

function excludeGraphifyOut(clone) {
  const exclude = path.join(clone, '.git', 'info', 'exclude')
  fs.mkdirSync(path.dirname(exclude), { recursive: true })
  const current = fs.existsSync(exclude) ? fs.readFileSync(exclude, 'utf8') : ''
  if (!current.split('\n').includes('/graphify-out/')) fs.appendFileSync(exclude, `${current && !current.endsWith('\n') ? '\n' : ''}/graphify-out/\n`)
}

/** Repositórios do workspace: links em repos/ que apontam para um clone. */
function workspaceRepos(root) {
  const dir = path.join(root, 'repos')
  if (!fs.existsSync(dir)) return []
  return fs.readdirSync(dir).sort().flatMap((alias) => {
    try {
      const clone = fs.realpathSync(path.join(dir, alias))
      return fs.existsSync(path.join(clone, '.git')) ? [{ alias, clone, slug: path.basename(clone) }] : []
    } catch {
      return []
    }
  })
}

async function buildRepo(repo, outDir, exec, locksDir) {
  const started = Date.now()
  const lock = path.join(locksDir, `${repo.slug}.lock`)
  const git = (args) => ['-w', '600', lock, 'git', '-C', repo.clone, ...args]
  const result = { alias: repo.alias, slug: repo.slug }
  try {
    fs.mkdirSync(locksDir, { recursive: true })
    await exec('flock', git(['fetch', '--quiet', 'origin']), { timeout: 300_000 }).catch(() => {})
    const ff = await exec('flock', git(['merge', '--ff-only', '--quiet', '@{u}']), { timeout: 120_000 }).catch((err) => err)
    if (ff instanceof Error) result.warning = 'clone não avançou (sem upstream ou divergente); grafo da versão atual'
    const { stdout: head } = await exec('git', ['-C', repo.clone, 'rev-parse', '--short', 'HEAD'], { timeout: 10_000 })
    result.commit = head.trim()
    excludeGraphifyOut(repo.clone)
    const { stdout, stderr } = await exec('flock', ['-w', '600', lock, GRAPHIFY, 'update', repo.clone], {
      cwd: repo.clone, timeout: 900_000, maxBuffer: 20 * 1024 * 1024,
    })
    Object.assign(result, parseRebuilt(`${stdout}\n${stderr}`))
    const report = path.join(repo.clone, 'graphify-out', 'GRAPH_REPORT.md')
    fs.mkdirSync(path.join(outDir, repo.alias), { recursive: true })
    if (fs.existsSync(report)) fs.copyFileSync(report, path.join(outDir, repo.alias, 'GRAPH_REPORT.md'))
    result.graph = path.join(repo.clone, 'graphify-out', 'graph.json')
  } catch (err) {
    result.error = String(err.stderr || err.message || err).trim().slice(-500)
  }
  result.duration_ms = Date.now() - started
  return result
}

/** Reconstrói o grafo do workspace. `exec` é injetável nos testes. */
async function buildKnowledge(slug, { reposRoot = '/repos', exec = run } = {}) {
  const root = workspaceRoot(slug, reposRoot)
  const outDir = graphDir(root)
  const started = new Date()
  writeStatus(root, { ...readStatus(root), state: 'running', started_at: started.toISOString() })
  const repos = []
  for (const repo of workspaceRepos(root)) repos.push(await buildRepo(repo, outDir, exec, path.join(reposRoot, '.locks')))
  const built = repos.filter((repo) => repo.graph && fs.existsSync(repo.graph))
  const graphs = built.map((repo) => repo.graph)
  const status = { state: 'done', started_at: started.toISOString(), repos: repos.map(({ graph, ...rest }) => rest) }
  try {
    const target = path.join(outDir, 'graph.json')
    if (graphs.length > 1) {
      const { stdout } = await exec(GRAPHIFY, ['merge-graphs', ...graphs, '--out', target], { timeout: 300_000 })
      Object.assign(status, parseRebuilt(stdout))
    } else if (graphs.length === 1) {
      fs.copyFileSync(graphs[0], target)
      Object.assign(status, { nodes: built[0].nodes, edges: built[0].edges })
    }
  } catch (err) {
    status.error = String(err.stderr || err.message || err).trim().slice(-500)
  }
  if (!graphs.length) status.error = status.error || 'nenhum repositório gerou grafo'
  if (status.error || repos.some((repo) => repo.error)) status.state = graphs.length ? 'partial' : 'error'
  status.finished_at = new Date().toISOString()
  status.duration_ms = Date.now() - started.getTime()
  writeStatus(root, status)
  return status
}

function startBuild(slug, options) {
  if (building.has(slug)) return false
  const job = buildKnowledge(slug, options)
    .then((status) => console.log(`[knowledge] ${slug}: ${status.state} (${status.nodes || 0} nós, ${status.duration_ms} ms)`))
    .catch((err) => console.error(`[knowledge] ${slug}: ${err.message}`))
    .finally(() => building.delete(slug))
  building.set(slug, job)
  return true
}

function listFiles(root) {
  const files = []
  const walk = (rel) => {
    for (const entry of fs.readdirSync(path.join(root, rel), { withFileTypes: true })) {
      if (files.length >= MAX_LIST) return
      const child = path.join(rel, entry.name)
      if (entry.isDirectory()) walk(child)
      else if (entry.isFile()) {
        const stat = fs.statSync(path.join(root, child))
        files.push({ path: child, size: stat.size, modified_at: stat.mtime.toISOString() })
      }
    }
  }
  for (const dir of BROWSABLE) if (fs.existsSync(path.join(root, dir))) walk(dir)
  return files
}

/** Lê um arquivo de knowledge/ ou memory/ (sem sair dessas pastas). */
function readFile(root, relPath) {
  const resolved = path.resolve(root, String(relPath || ''))
  const allowed = BROWSABLE.some((dir) => resolved.startsWith(`${path.join(root, dir)}/`))
  if (!allowed) throw new Error('caminho fora de knowledge/ e memory/')
  const real = fs.realpathSync(resolved)
  if (!BROWSABLE.some((dir) => real.startsWith(`${path.join(root, dir)}/`))) throw new Error('caminho fora de knowledge/ e memory/')
  const size = fs.statSync(real).size
  const fd = fs.openSync(real, 'r')
  const buffer = Buffer.alloc(Math.min(size, MAX_FILE_BYTES))
  fs.readSync(fd, buffer, 0, buffer.length, 0)
  fs.closeSync(fd)
  return { path: relPath, size, truncated: size > MAX_FILE_BYTES, content: buffer.toString('utf8') }
}

async function tryHandle(req, res, { json }) {
  const url = new URL(req.url || '/', 'http://localhost')
  const match = url.pathname.match(/^\/workspaces\/([^/]+)\/knowledge(\/build|\/file)?$/)
  if (!match) return false
  try {
    const slug = decodeURIComponent(match[1])
    const root = workspaceRoot(slug)
    if (req.method === 'POST' && match[2] === '/build') {
      const started = startBuild(slug)
      json(res, 202, { started, running: building.has(slug) })
    } else if (req.method === 'GET' && match[2] === '/file') {
      json(res, 200, readFile(root, url.searchParams.get('path')))
    } else if (req.method === 'GET' && !match[2]) {
      json(res, 200, { status: { ...readStatus(root), running: building.has(slug) }, files: fs.existsSync(root) ? listFiles(root) : [] })
    } else {
      return false
    }
  } catch (err) {
    json(res, 400, { error: err.message })
  }
  return true
}

module.exports = { buildKnowledge, listFiles, parseRebuilt, readFile, tryHandle, workspaceRepos }
