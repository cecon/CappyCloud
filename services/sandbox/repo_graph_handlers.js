'use strict'

const { graphForRepo } = require('./repo_graph/response')

async function tryHandle(req, res, { json }) {
  if (req.method !== 'GET' || !req.url) return false
  const url = new URL(req.url, 'http://localhost')
  const match = url.pathname.match(/^\/repos\/([^/]+)\/graph$/)
  if (!match) return false
  try {
    await json(res, 200, await graphForRepo(match[1], url.searchParams))
  } catch (err) {
    await json(res, 500, { error: err.message || String(err) })
  }
  return true
}

module.exports = { tryHandle }
