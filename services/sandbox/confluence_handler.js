'use strict'
// Read-only HTTP proxy for a configured Confluence-compatible documentation site.

const BASE_URL = (process.env.CONFLUENCE_BASE_URL || '').replace(/\/$/, '')
const MAIN_MENU_URL = process.env.CONFLUENCE_MAIN_MENU_URL || ''
const MAX_TEXT_CHARS = 18000

function configuredBaseUrl(url) {
  const value = (url.searchParams.get('base_url') || BASE_URL || '').trim().replace(/\/$/, '')
  if (!value) return ''
  const parsed = new URL(value)
  if (!['http:', 'https:'].includes(parsed.protocol)) {
    throw new Error('CONFLUENCE_BASE_URL deve usar http(s)')
  }
  return value
}

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

function absoluteUrl(baseUrl, href) {
  return href.startsWith('http') ? href : `${baseUrl}${href.startsWith('/') ? '' : '/'}${href}`
}

function clip(value, limit = MAX_TEXT_CHARS) {
  const text = String(value || '').trim()
  return text.length <= limit ? text : `${text.slice(0, limit).trim()}\n...[truncado]`
}

function pageIdFromUrl(baseUrl, urlOrId) {
  const value = String(urlOrId || '').trim()
  if (/^\d+$/.test(value)) return value
  const parsed = new URL(value)
  if (parsed.hostname !== new URL(baseUrl).hostname) {
    throw new Error('URL fora do Confluence configurado')
  }
  const pageId = parsed.searchParams.get('pageId')
  if (pageId) return pageId
  const match = parsed.pathname.match(/\/pages\/(\d+)/)
  if (match) return match[1]
  throw new Error('Não foi possível extrair pageId')
}

async function resolvePageId(baseUrl, urlOrId) {
  try {
    return pageIdFromUrl(baseUrl, urlOrId)
  } catch (err) {
    const value = String(urlOrId || '').trim()
    const parsed = new URL(value)
    if (parsed.hostname !== new URL(baseUrl).hostname) throw err
    const html = await fetchText(value)
    const metaMatch = html.match(/<meta\s+name="ajs-page-id"\s+content="(\d+)"/i)
    if (metaMatch) return metaMatch[1]
    throw err
  }
}

function pageUrl(page, baseUrl) {
  const links = page._links || {}
  const webui = links.webui || ''
  const base = links.base || baseUrl
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

function compactPage(page, baseUrl) {
  return {
    id: page.id,
    title: page.title,
    space: page.space && page.space.key,
    url: pageUrl(page, baseUrl),
    version: page.version && page.version.number,
    text: clip(pageText(page)),
  }
}

function parseSiteSearchResults(baseUrl, html, limit) {
  return parseSiteSearchResultsForSpace(baseUrl, html, limit, '')
}

function parseSiteSearchResultsForSpace(baseUrl, html, limit, space) {
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
    if (expectedSpace && expectedSpace !== 'all' && expectedSpace !== resultSpace.toLowerCase()) {
      continue
    }

    const resultUrl = absoluteUrl(baseUrl, href.replace(/&amp;/g, '&'))
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

async function siteSearch(baseUrl, query, limit, space) {
  const html = await fetchText(`${baseUrl}/dosearchsite.action`, { queryString: query })
  return parseSiteSearchResultsForSpace(baseUrl, html, limit, space)
}

async function tryHandle(req, res, { json }) {
  const url = new URL(req.url, `http://${req.headers.host}`)
  const pathname = url.pathname
  if (req.method !== 'GET' || !pathname.startsWith('/confluence/')) return false

  try {
    const baseUrl = configuredBaseUrl(url)
    if (!baseUrl) {
      await json(res, 503, { error: 'CONFLUENCE_BASE_URL não configurada' })
      return true
    }

    if (pathname === '/confluence/main') {
      const mainUrl = url.searchParams.get('main_url') || MAIN_MENU_URL
      if (!mainUrl) {
        await json(res, 503, { error: 'CONFLUENCE_MAIN_MENU_URL não configurada' })
        return true
      }
      const page = await fetchJson(`${baseUrl}/rest/api/content/${pageIdFromUrl(baseUrl, mainUrl)}`, {
        expand: 'body.storage,body.view,version,space,ancestors',
      })
      await json(res, 200, compactPage(page, baseUrl))
      return true
    }

    if (pathname === '/confluence/page') {
      const id = await resolvePageId(baseUrl, url.searchParams.get('id') || url.searchParams.get('url'))
      const page = await fetchJson(`${baseUrl}/rest/api/content/${id}`, {
        expand: 'body.storage,body.view,version,space,ancestors',
      })
      await json(res, 200, compactPage(page, baseUrl))
      return true
    }

    if (pathname === '/confluence/search') {
      const q = url.searchParams.get('q') || ''
      const limit = Math.max(1, Math.min(Number(url.searchParams.get('limit') || 5), 10))
      const space = url.searchParams.get('space') || 'all'
      if (!q) {
        await json(res, 400, { error: 'q is required' })
        return true
      }
      const escaped = q.replace(/"/g, '\\"')
      const spaceFilter = space && space !== 'all' ? `space="${space}" AND ` : ''
      const cql = `${spaceFilter}type=page AND text ~ "${escaped}"`
      const data = await fetchJson(`${baseUrl}/rest/api/content/search`, {
        cql,
        limit,
        expand: 'body.storage,body.view,version,space',
      })
      let results = (data.results || []).map(page => ({
        id: page.id,
        title: page.title,
        space: page.space && page.space.key,
        url: pageUrl(page, baseUrl),
        excerpt: clip(pageText(page), 900),
      }))
      let total = data.size
      let source = 'rest-cql'

      if (results.length === 0) {
        const fallback = await siteSearch(baseUrl, q, limit, space)
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
