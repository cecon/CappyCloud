/**
 * Cliente HTTP para a API CappyCloud (paths relativos `/api` com proxy Vite).
 */

const TOKEN_KEY = 'cappycloud_token'
let loginRedirectInFlight = false

/**
 * Extrai texto legível do corpo JSON de erro da FastAPI (422, etc.).
 * Evita `[object Object]` quando `msg` é objeto ou a lista contém strings misturadas.
 */
export function formatApiErrorPayload(data: unknown): string {
  if (typeof data !== 'object' || data === null) {
    return typeof data === 'string' ? data.trim() : 'Pedido inválido'
  }
  if (!('detail' in data)) {
    return stringifyNonEmpty(data)
  }
  const detail = (data as { detail: unknown }).detail

  if (typeof detail === 'string') {
    return detail.trim()
  }

  if (Array.isArray(detail)) {
    const parts: string[] = []
    for (const item of detail) {
      if (typeof item === 'string') {
        parts.push(item)
        continue
      }
      if (typeof item === 'object' && item !== null) {
        const o = item as Record<string, unknown>
        const loc = o.loc
        const locStr =
          Array.isArray(loc) && loc.length > 0
            ? ` (${loc.filter((x) => x !== 'body').join('.')})`
            : ''
        const msg = o.msg
        if (typeof msg === 'string') {
          parts.push(msg + locStr)
          continue
        }
        if (msg != null && typeof msg === 'object') {
          parts.push(JSON.stringify(msg) + locStr)
          continue
        }
        if (msg != null) {
          parts.push(String(msg) + locStr)
          continue
        }
        parts.push(JSON.stringify(item))
        continue
      }
      parts.push(String(item))
    }
    const out = parts.filter(Boolean).join(' · ')
    return out || 'Pedido inválido'
  }

  if (typeof detail === 'object' && detail !== null) {
    return stringifyNonEmpty(detail)
  }

  return String(detail ?? '').trim()
}

/**
 * Mensagem segura para mostrar ao utilizador a partir de qualquer valor em `catch`.
 */
export function errorToUserMessage(e: unknown): string {
  if (e instanceof Error) {
    return e.message.trim() || 'Erro desconhecido'
  }
  if (typeof e === 'string') {
    return e.trim() || 'Erro desconhecido'
  }
  try {
    return stringifyNonEmpty(e) || 'Falha inesperada. Tente novamente ou consulte os logs da API.'
  } catch {
    return String(e).trim() || 'Falha inesperada. Tente novamente ou consulte os logs da API.'
  }
}

function stringifyNonEmpty(value: unknown): string {
  try {
    const text = JSON.stringify(value)
    return text && text !== '{}' && text !== '[]' ? text : ''
  } catch {
    return ''
  }
}

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string | null): void {
  if (token) localStorage.setItem(TOKEN_KEY, token)
  else localStorage.removeItem(TOKEN_KEY)
}

export function redirectToLogin(): void {
  setToken(null)
  if (loginRedirectInFlight) return
  loginRedirectInFlight = true
  if (window.location.pathname === '/login') return
  window.location.replace('/login')
}

/** Lançado quando a API responde 401. Sinaliza que o token expirou ou é inválido. */
export class AuthError extends Error {
  constructor() {
    super('Sessão expirada. Por favor, faça login novamente.')
    this.name = 'AuthError'
  }
}

/**
 * Wrapper sobre `fetch` que lança `AuthError` em 401
 * e erros genéricos nos outros casos de falha.
 */
export async function apiFetch(url: string, init?: RequestInit): Promise<Response> {
  const res = await fetch(url, init)
  if (res.status === 401) throw new AuthError()
  return res
}
