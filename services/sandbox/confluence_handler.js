'use strict'
// Read-only HTTP proxy for public Linx Share/Confluence docs.

const BASE_URL = 'https://share.linx.com.br'
const MAIN_MENU_URL = `${BASE_URL}/pages/viewpage.action?pageId=11570159`
const MAX_TEXT_CHARS = 18000

function stripHtml(value) {
  return String(value || '')
    .replace(/<script[\s\S]*?<\/script>/gi, ' ')
    .replace(/<style[\s\S]*?<\/style>/gi, ' ')
    .replace(/<br\s*\/?>/gi, '\n')
    .replace(/<\/(p|div|h[1-6]|li|tr)>/gi, '\n')
    .replace(/<[^>]+>/g, ' ')
    .replace(/&nbsp;/g, ' ')
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/[ \t]+/g, ' ')
    .replace(/\n{3,}/g, '\n\n')
    .trim()
}

function absoluteUrl(href) {
  return href.startsWith('http') ? href : `${BASE_URL}${href.startsWith('/') ? '' : '/'}${href}`
}

function clip(value, limit = MAX_TEXT_CHARS) {
  const text = String(value || '').trim()
  return text.length <= limit ? text : `${text.slice(0, limit).trim()}\n...[truncado]`
}

function pageIdFromUrl(urlOrId) {
  const value = String(urlOrId || '').trim()
  if (/^\d+$/.test(value)) return value
  const parsed = new URL(value)
  if (parsed.hostname !== 'share.linx.com.br') throw new Error('URL fora de share.linx.com.br')
  const pageId = parsed.searchParams.get('pageId')
  if (pageId) return pageId
  const match = parsed.pathname.match(/\/pages\/(\d+)/)
  if (match) return match[1]
  throw new Error('Não foi possível extrair pageId')
}

async function resolvePageId(urlOrId) {
  try {
    return pageIdFromUrl(urlOrId)
  } catch (err) {
    const value = String(urlOrId || '').trim()
    const parsed = new URL(value)
    if (parsed.hostname !== 'share.linx.com.br') throw err
    const html = await fetchText(value)
    const metaMatch = html.match(/<meta\s+name="ajs-page-id"\s+content="(\d+)"/i)
    if (metaMatch) return metaMatch[1]
    throw err
  }
}

function pageUrl(page) {
  const links = page._links || {}
  const webui = links.webui || ''
  const base = links.base || BASE_URL
  return webui.startsWith('/') ? `${base.replace(/\/$/, '')}${webui}` : webui
}

function pageText(page) {
  const body = page.body || {}
  const storageText = stripHtml(body.storage && body.storage.value)
  const viewText = stripHtml(body.view && body.view.value)
  return viewText.length > storageText.length ? viewText : storageText
}

async function fetchJson(url, params = {}) {
  const full = new URL(url)
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '') {
      full.searchParams.set(key, String(value))
    }
  }
  const resp = await fetch(full, { headers: { Accept: 'application/json' } })
  const text = await resp.text()
  if (resp.status >= 400) {
    throw new Error(`Confluence HTTP ${resp.status}: ${text.slice(0, 300)}`)
  }
  return JSON.parse(text)
}

async function fetchText(url, params = {}) {
  const full = new URL(url)
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '') {
      full.searchParams.set(key, String(value))
    }
  }
  const resp = await fetch(full, { headers: { Accept: 'text/html,application/xhtml+xml' } })
  const text = await resp.text()
  if (resp.status >= 400) {
    throw new Error(`Confluence HTTP ${resp.status}: ${text.slice(0, 300)}`)
  }
  return text
}

function compactPage(page) {
  return {
    id: page.id,
    title: page.title,
    space: page.space && page.space.key,
    url: pageUrl(page),
    version: page.version && page.version.number,
    text: clip(pageText(page)),
  }
}

function parseSiteSearchResults(html, limit) {
  return parseSiteSearchResultsForSpace(html, limit, '')
}

function parseSiteSearchResultsForSpace(html, limit, space) {
  const totalMatch = html.match(/data-totalsize="(\d+)"/)
  const total = totalMatch ? Number(totalMatch[1]) : undefined
  const results = []
  const seen = new Set()
  const expectedSpace = String(space || '').trim().toLowerCase()
  const itemRegex = /<li\b[\s\S]*?<\/li>/gi
  let match

  while ((match = itemRegex.exec(html))) {
    const item = match[0]
    const linkMatch = item.match(/<a\b[^>]*class="[^"]*\bsearch-result-link\b[^"]*"[^>]*href="([^"]+)"[^>]*data-type="([^"]+)"[^>]*>([\s\S]*?)<\/a>/i)
    if (!linkMatch) continue
    const [, href, type, rawTitle] = linkMatch
    if (type !== 'page') continue

    const spaceMatch = item.match(/<a class="container"[^>]*>([\s\S]*?)<\/a>/i)
    const resultSpace = stripHtml(spaceMatch && spaceMatch[1])
    if (
      expectedSpace &&
      expectedSpace !== 'all' &&
      ![expectedSpace, 'postos'].includes(resultSpace.toLowerCase())
    ) {
      continue
    }

    const resultUrl = absoluteUrl(href.replace(/&amp;/g, '&'))
    if (seen.has(resultUrl)) continue
    seen.add(resultUrl)

    const highlightMatch = item.match(/<div class="highlights">([\s\S]*?)<\/div>/i)
    results.push({
      id: null,
      title: stripHtml(rawTitle),
      space: resultSpace,
      url: resultUrl,
      excerpt: clip(stripHtml(highlightMatch && highlightMatch[1]), 900),
    })
    if (results.length >= limit) break
  }

  return { total, results }
}

async function siteSearch(query, limit, space) {
  const html = await fetchText(`${BASE_URL}/dosearchsite.action`, { queryString: query })
  return parseSiteSearchResultsForSpace(html, limit, space)
}

async function tryHandle(req, res, { json }) {
  const url = new URL(req.url, `http://${req.headers.host}`)
  const pathname = url.pathname
  if (req.method !== 'GET' || !pathname.startsWith('/confluence/')) return false

  try {
    if (pathname === '/confluence/main') {
      const page = await fetchJson(`${BASE_URL}/rest/api/content/${pageIdFromUrl(MAIN_MENU_URL)}`, {
        expand: 'body.storage,body.view,version,space,ancestors',
      })
      await json(res, 200, compactPage(page))
      return true
    }

    if (pathname === '/confluence/page') {
      const id = await resolvePageId(url.searchParams.get('id') || url.searchParams.get('url'))
      const page = await fetchJson(`${BASE_URL}/rest/api/content/${id}`, {
        expand: 'body.storage,body.view,version,space,ancestors',
      })
      await json(res, 200, compactPage(page))
      return true
    }

    if (pathname === '/confluence/search') {
      const q = url.searchParams.get('q') || ''
      const limit = Math.max(1, Math.min(Number(url.searchParams.get('limit') || 5), 10))
      const space = url.searchParams.get('space') || 'POSTOS'
      if (!q) {
        await json(res, 400, { error: 'q is required' })
        return true
      }
      const escaped = q.replace(/"/g, '\\"')
      const cql = `space="${space}" AND type=page AND text ~ "${escaped}"`
      const data = await fetchJson(`${BASE_URL}/rest/api/content/search`, {
        cql,
        limit,
        expand: 'body.storage,body.view,version,space',
      })
      let results = (data.results || []).map(page => ({
        id: page.id,
        title: page.title,
        space: page.space && page.space.key,
        url: pageUrl(page),
        excerpt: clip(pageText(page), 900),
      }))
      let total = data.size
      let source = 'rest-cql'

      if (results.length === 0) {
        const fallback = await siteSearch(q, limit, space)
        results = fallback.results
        total = fallback.total
        source = 'site-search'
      }

      await json(res, 200, {
        query: q,
        source,
        total,
        count: results.length,
        results,
      })
      return true
    }

    await json(res, 404, { error: 'Unknown confluence endpoint' })
    return true
  } catch (err) {
    await json(res, 502, { error: err.message })
    return true
  }
}

module.exports = { tryHandle }
