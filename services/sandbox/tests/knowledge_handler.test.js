'use strict'
// Usa symlinks POSIX (roda no container do sandbox ou em Linux):
//   node --test services/sandbox/tests/knowledge_handler.test.js
const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('fs')
const os = require('os')
const path = require('path')

const { buildKnowledge, listFiles, parseRebuilt, readFile } = require('../knowledge_handler')

const posix = process.platform !== 'win32'

/** Workspace "loja" com dois repositórios (links para clones com .git). */
function setup() {
  const reposRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'cappy-knowledge-'))
  const ws = path.join(reposRoot, 'workspaces', 'loja')
  for (const slug of ['seller', 'pdv']) {
    fs.mkdirSync(path.join(reposRoot, slug, '.git'), { recursive: true })
    fs.mkdirSync(path.join(ws, 'repos'), { recursive: true })
    fs.symlinkSync(path.join(reposRoot, slug), path.join(ws, 'repos', slug))
  }
  return { reposRoot, ws }
}

/** git/graphify falsos: `update` grava graphify-out no clone como o graphify real. */
function fakeExec(calls, { failUpdateOf = '', unchanged = false } = {}) {
  return async (cmd, args) => {
    calls.push([cmd, ...args].join(' '))
    const graphifyArgs = cmd === 'flock' ? args.slice(3) : [cmd, ...args]
    if (graphifyArgs[0] === 'git' && graphifyArgs.includes('rev-parse')) return { stdout: 'abc1234\n', stderr: '' }
    if (cmd === 'git' && args.includes('rev-parse')) return { stdout: 'abc1234\n', stderr: '' }
    if (graphifyArgs[1] === 'update') {
      const clone = graphifyArgs[2]
      if (failUpdateOf && clone.endsWith(failUpdateOf)) throw Object.assign(new Error('boom'), { stderr: 'graphify quebrou' })
      fs.mkdirSync(path.join(clone, 'graphify-out'), { recursive: true })
      fs.writeFileSync(path.join(clone, 'graphify-out', 'graph.json'), '{"nodes":[]}')
      fs.writeFileSync(path.join(clone, 'graphify-out', 'GRAPH_REPORT.md'), `# ${path.basename(clone)}`)
      if (unchanged) return { stdout: '[graphify watch] No code-graph topology changes detected; outputs left untouched.', stderr: '' }
      return { stdout: '[graphify watch] Rebuilt: 40 nodes, 70 edges, 3 communities', stderr: '' }
    }
    if (args[0] === 'merge-graphs') {
      fs.writeFileSync(args[args.indexOf('--out') + 1], '{"merged":true}')
      return { stdout: 'Merged 2 graphs -> 80 nodes, 140 edges', stderr: '' }
    }
    return { stdout: '', stderr: '' }
  }
}

test('lê os números da saída do graphify', () => {
  assert.deepEqual(parseRebuilt('Rebuilt: 400 nodes, 715 edges, 22 communities'), { nodes: 400, edges: 715, communities: 22 })
  assert.deepEqual(parseRebuilt('Merged 2 graphs -> 863 nodes, 1731 edges'), { nodes: 863, edges: 1731, communities: 0 })
  assert.deepEqual(parseRebuilt('nada'), {})
})

test('gera o grafo de cada repositório, junta e grava o status', { skip: !posix }, async () => {
  const { reposRoot, ws } = setup()
  const calls = []
  const status = await buildKnowledge('loja', { reposRoot, exec: fakeExec(calls) })

  assert.equal(status.state, 'done')
  assert.equal(status.nodes, 80)
  assert.deepEqual(status.repos.map((r) => [r.alias, r.nodes, r.commit]), [['pdv', 40, 'abc1234'], ['seller', 40, 'abc1234']])
  assert.equal(fs.readFileSync(path.join(ws, 'knowledge/graphify/graph.json'), 'utf8'), '{"merged":true}')
  assert.equal(fs.readFileSync(path.join(ws, 'knowledge/graphify/seller/GRAPH_REPORT.md'), 'utf8'), '# seller')
  assert.equal(JSON.parse(fs.readFileSync(path.join(ws, 'knowledge/graphify/status.json'), 'utf8')).state, 'done')
  // Clone fica sem arquivo novo no git e com a trava do repositório.
  assert.match(fs.readFileSync(path.join(reposRoot, 'seller/.git/info/exclude'), 'utf8'), /\/graphify-out\//)
  assert.ok(calls.some((c) => c.startsWith(`flock -w 600 ${path.join(reposRoot, '.locks', 'seller.lock')} graphify update`)))
})

test('falha em um repositório vira status parcial com o erro', { skip: !posix }, async () => {
  const { reposRoot } = setup()
  const status = await buildKnowledge('loja', { reposRoot, exec: fakeExec([], { failUpdateOf: 'pdv' }) })

  assert.equal(status.state, 'partial')
  assert.equal(status.repos.find((r) => r.alias === 'pdv').error, 'graphify quebrou')
  assert.equal(status.nodes, 40)
})

test('lista e lê só knowledge/ e memory/', { skip: !posix }, async () => {
  const { reposRoot, ws } = setup()
  await buildKnowledge('loja', { reposRoot, exec: fakeExec([]) })
  fs.mkdirSync(path.join(ws, 'memory'), { recursive: true })
  fs.writeFileSync(path.join(ws, 'memory', 'nota.md'), 'lembrar')

  const files = listFiles(ws).map((f) => f.path)
  assert.ok(files.includes('knowledge/graphify/status.json'))
  assert.ok(files.includes('memory/nota.md'))
  assert.ok(!files.some((f) => f.startsWith('repos/')))
  assert.equal(readFile(ws, 'memory/nota.md').content, 'lembrar')
  assert.throws(() => readFile(ws, 'repos/seller/.git/config'), /fora de knowledge/)
  assert.throws(() => readFile(ws, 'knowledge/../CLAUDE.md'), /fora de knowledge/)
})

test('sem mudança no código mantém a contagem da rodada anterior', { skip: !posix }, async () => {
  const { reposRoot } = setup()
  await buildKnowledge('loja', { reposRoot, exec: fakeExec([]) })
  const status = await buildKnowledge('loja', { reposRoot, exec: fakeExec([], { unchanged: true }) })

  assert.equal(status.state, 'done')
  assert.deepEqual(status.repos.map((r) => [r.alias, r.nodes, r.unchanged]), [['pdv', 40, true], ['seller', 40, true]])
})

test('resumo conta commits novos desde o grafo e repositórios sem grafo', { skip: !posix }, async () => {
  const { reposRoot, ws } = setup()
  await buildKnowledge('loja', { reposRoot, exec: fakeExec([]) })
  fs.mkdirSync(path.join(reposRoot, 'novo', '.git'), { recursive: true })
  fs.symlinkSync(path.join(reposRoot, 'novo'), path.join(ws, 'repos', 'novo'))
  const counts = { pdv: '3\n', seller: '0\n' }
  const exec = async (cmd, args) => ({ stdout: counts[path.basename(args[1])] ?? '', stderr: '' })

  const { graphSummary } = require('../knowledge_handler')
  const summary = await graphSummary(ws, exec)

  assert.equal(summary.state, 'done')
  assert.equal(summary.behind, 3)
  assert.deepEqual(summary.repos.map((r) => [r.alias, r.behind]), [['pdv', 3], ['seller', 0]])
  assert.deepEqual(summary.missing, ['novo'])
})

test('tempo esgotado vira mensagem clara', { skip: !posix }, async () => {
  const { reposRoot } = setup()
  const base = fakeExec([])
  const exec = async (cmd, args, opts) => {
    if (cmd === 'flock' && args[4] === 'update') throw Object.assign(new Error('killed'), { killed: true, stderr: 'warning: …' })
    return base(cmd, args, opts)
  }
  const status = await buildKnowledge('loja', { reposRoot, exec })

  assert.equal(status.state, 'error')
  assert.match(status.repos[0].error, /^tempo esgotado após \d+ min/)
})

test('gerações pedidas juntas rodam uma de cada vez', { skip: !posix }, async () => {
  const { startBuild } = require('../knowledge_handler')
  const { reposRoot } = setup()
  const second = path.join(reposRoot, 'workspaces', 'pdv')
  fs.mkdirSync(path.join(second, 'repos'), { recursive: true })
  fs.symlinkSync(path.join(reposRoot, 'pdv'), path.join(second, 'repos', 'pdv'))
  let running = 0
  let peak = 0
  const base = fakeExec([])
  const exec = async (cmd, args, opts) => {
    running += 1
    peak = Math.max(peak, running)
    await new Promise((resolve) => setTimeout(resolve, 5))
    running -= 1
    return base(cmd, args, opts)
  }

  assert.equal(startBuild('loja', { reposRoot, exec }), true)
  assert.equal(startBuild('pdv', { reposRoot, exec }), true)
  assert.equal(startBuild('loja', { reposRoot, exec }), false) // já na fila
  await new Promise((resolve) => setTimeout(resolve, 400))

  assert.equal(peak, 1)
  for (const slug of ['loja', 'pdv']) {
    const status = JSON.parse(fs.readFileSync(path.join(reposRoot, 'workspaces', slug, 'knowledge/graphify/status.json'), 'utf8'))
    assert.equal(status.state, 'done')
  }
})
