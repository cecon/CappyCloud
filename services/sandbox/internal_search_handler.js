'use strict'
// ──────────────────────────────────────────────────────────────
// Proxy de busca para a API interna do CappyCloud.
//
// Endpoints:
//   GET /skills/search          → /api/skills/_search/internal
//   GET /document-graph/search  → /api/document-graph/_search/internal
// ──────────────────────────────────────────────────────────────

const ROUTES = {
  '/skills/search': '/api/skills/_search/internal',
  '/document-graph/search': '/api/document-graph/_search/internal',
}

async function proxySearch(res, { json, url }, apiPath) {
  const q = url.searchParams.get('q') || ''
  const limit = url.searchParams.get('limit') || '5'
  if (!q) return json(res, 400, { error: 'q is required' })

  const apiHost = process.env.API_HOST || 'cappycloud-api'
  const apiPort = process.env.API_PORT_INTERNAL || '8080'
  const internalToken = process.env.INTERNAL_API_TOKEN || ''
  const params = new URLSearchParams({ q, limit })
  for (const repoId of url.searchParams.getAll('repo_id')) {
    if (repoId) params.append('repo_id', repoId)
  }
  const apiUrl = `http://${apiHost}:${apiPort}${apiPath}?${params}`
  try {
    const resp = await fetch(apiUrl, {
      headers: internalToken ? { 'X-Internal-Token': internalToken } : {},
    })
    const text = await resp.text()
    if (resp.status >= 400) {
      return json(res, resp.status, { error: 'API error', detail: text.slice(0, 300) })
    }
    res.writeHead(200, { 'Content-Type': 'application/json' })
    return res.end(text)
  } catch (err) {
    return json(res, 502, { error: 'API unreachable', detail: err.message })
  }
}

/**
 * Trata GET /skills/search e GET /document-graph/search.
 * `url` é o URL já parseado pelo servidor.
 * @returns {Promise<boolean>} true se a rota foi tratada
 */
async function tryHandle(req, res, { json, url }) {
  if (req.method !== 'GET') return false
  const apiPath = Object.prototype.hasOwnProperty.call(ROUTES, url.pathname)
    ? ROUTES[url.pathname]
    : ''
  if (!apiPath) return false
  await proxySearch(res, { json, url }, apiPath)
  return true
}

module.exports = { tryHandle }
