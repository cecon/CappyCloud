'use strict'

function authHeader() {
  const explicit = (process.env.CONFLUENCE_AUTHORIZATION || '').trim()
  if (explicit) return explicit

  const basicToken = (process.env.CONFLUENCE_BASIC_TOKEN || '').trim()
  if (basicToken) return `Basic ${basicToken}`

  const pat = (process.env.CONFLUENCE_PAT || '').trim()
  if (pat) return `Bearer ${pat}`

  const email = (process.env.CONFLUENCE_EMAIL || '').trim()
  const token = (process.env.CONFLUENCE_API_TOKEN || '').trim()
  if (email && token) {
    return `Basic ${Buffer.from(`${email}:${token}`, 'utf8').toString('base64')}`
  }
  return ''
}

function requestHeaders(accept) {
  const headers = { Accept: accept }
  const authorization = authHeader()
  if (authorization) headers.Authorization = authorization
  return headers
}

module.exports = { authHeader, requestHeaders }
