'use strict'
// Memória dos workspaces, guardada no serviço agentmemory (AGENTMEMORY_URL).
//
//   POST /memory/save    {workspace, content, type?, concepts?, files?}  → grava
//   GET  /memory/search?workspace=&q=&limit=                             → busca (conteúdo completo)
//   GET  /workspaces/:slug/memory                                       → lista (admin)
//
// O agentmemory não separa por projeto na busca, só por agentId quando o
// servidor roda com AGENTMEMORY_AGENT_SCOPE=isolated. Por isso cada workspace
// é um agentId próprio (`ws-<slug>`), e o conteúdo só volta se o agentId da
// memória bater com o do workspace pedido. O agente chama estas rotas com curl
// (funciona igual no Claude CLI e no openclaude).

const WORKSPACE_SLUG = /^[a-z0-9][a-z0-9-]{1,62}$/
const TYPES = new Set(['pattern', 'preference', 'architecture', 'bug', 'workflow', 'fact'])
const MAX_CONTENT = 8000

function agentIdFor(slug) {
  if (!WORKSPACE_SLUG.test(String(slug || ''))) throw Object.assign(new Error(`workspace inválido: ${slug}`), { status: 400 })
  return `ws-${slug}`
}

function listOf(value) {
  const items = Array.isArray(value) ? value : String(value || '').split(',')
  return items.map((item) => String(item).trim()).filter(Boolean).slice(0, 20)
}

/** Cliente REST do agentmemory. `fetchImpl` é injetável nos testes. */
function createClient({ url = process.env.AGENTMEMORY_URL, secret = process.env.AGENTMEMORY_SECRET, fetchImpl = fetch } = {}) {
  return async (path, { method = 'GET', body } = {}) => {
    if (!url) throw Object.assign(new Error('memória indisponível: AGENTMEMORY_URL não configurado'), { status: 503 })
    const response = await fetchImpl(`${url.replace(/\/$/, '')}/agentmemory${path}`, {
      method,
      headers: { Authorization: `Bearer ${secret || ''}`, 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: AbortSignal.timeout(20_000),
    })
    const data = await response.json().catch(() => ({}))
    if (!response.ok) throw Object.assign(new Error(data.error || `agentmemory respondeu ${response.status}`), { status: 502 })
    return data
  }
}

function publicMemory(memory) {
  return {
    id: memory.id,
    type: memory.type,
    content: memory.content,
    concepts: memory.concepts || [],
    files: memory.files || [],
    created_at: memory.createdAt,
    updated_at: memory.updatedAt,
  }
}

async function saveMemory(call, { workspace, content, type, concepts, files }) {
  const agentId = agentIdFor(workspace)
  const text = String(content || '').trim()
  if (!text) throw Object.assign(new Error('content é obrigatório'), { status: 400 })
  const data = await call('/remember', {
    method: 'POST',
    body: {
      content: text.slice(0, MAX_CONTENT),
      type: TYPES.has(type) ? type : 'fact',
      concepts: listOf(concepts),
      files: listOf(files),
      project: workspace,
      agentId,
    },
  })
  return { saved: true, id: data.memory?.id }
}

async function searchMemory(call, { workspace, q, limit }) {
  const agentId = agentIdFor(workspace)
  const query = String(q || '').trim()
  if (!query) throw Object.assign(new Error('q é obrigatório'), { status: 400 })
  const size = Math.min(Math.max(Number(limit) || 5, 1), 10)
  const found = await call('/smart-search', { method: 'POST', body: { query, limit: size, agentId, includeLessons: false } })
  const results = []
  for (const hit of found.results || []) {
    const id = String(hit.obsId || '')
    if (!id.startsWith('mem_')) continue
    const { memory } = await call(`/memories/${encodeURIComponent(id)}`).catch(() => ({}))
    if (memory && memory.agentId === agentId) results.push({ ...publicMemory(memory), score: hit.score })
  }
  return { workspace, results }
}

async function listMemories(call, workspace) {
  const agentId = agentIdFor(workspace)
  const data = await call(`/memories?agentId=${encodeURIComponent(agentId)}`)
  const memories = (data.memories || []).filter((memory) => memory.agentId === agentId)
  memories.sort((a, b) => String(b.updatedAt || b.createdAt).localeCompare(String(a.updatedAt || a.createdAt)))
  return { workspace, total: memories.length, memories: memories.slice(0, 200).map(publicMemory) }
}

async function tryHandle(req, res, { json, readBody }, call = createClient()) {
  const url = new URL(req.url || '/', 'http://localhost')
  const listMatch = url.pathname.match(/^\/workspaces\/([^/]+)\/memory$/)
  try {
    if (req.method === 'POST' && url.pathname === '/memory/save') {
      json(res, 200, await saveMemory(call, await readBody(req)))
    } else if (req.method === 'GET' && url.pathname === '/memory/search') {
      json(res, 200, await searchMemory(call, Object.fromEntries(url.searchParams)))
    } else if (req.method === 'GET' && listMatch) {
      json(res, 200, await listMemories(call, decodeURIComponent(listMatch[1])))
    } else {
      return false
    }
  } catch (err) {
    json(res, err.status || 500, { error: err.message })
  }
  return true
}

module.exports = { createClient, listMemories, saveMemory, searchMemory, tryHandle }
