/**
 * Cliente HTTP para a API CappyCloud (paths relativos `/api` com proxy Vite).
 */

const TOKEN_KEY = 'cappycloud_token'

/**
 * Extrai texto legível do corpo JSON de erro da FastAPI (422, etc.).
 * Evita `[object Object]` quando `msg` é objeto ou a lista contém strings misturadas.
 */
function formatApiErrorPayload(data: unknown): string {
  if (typeof data !== 'object' || data === null) {
    return 'Pedido inválido'
  }
  if (!('detail' in data)) {
    return JSON.stringify(data)
  }
  const detail = (data as { detail: unknown }).detail

  if (typeof detail === 'string') {
    return detail
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
    return JSON.stringify(detail)
  }

  return String(detail ?? 'Pedido inválido')
}

/**
 * Mensagem segura para mostrar ao utilizador a partir de qualquer valor em `catch`.
 */
export function errorToUserMessage(e: unknown): string {
  if (e instanceof Error) {
    return e.message || 'Erro desconhecido'
  }
  if (typeof e === 'string') {
    return e
  }
  try {
    return JSON.stringify(e)
  } catch {
    return String(e)
  }
}

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string | null): void {
  if (token) localStorage.setItem(TOKEN_KEY, token)
  else localStorage.removeItem(TOKEN_KEY)
}

export async function loginRequest(email: string, password: string): Promise<string> {
  const body = new URLSearchParams()
  body.set('username', email)
  body.set('password', password)
  const res = await fetch('/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: body.toString(),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    const text = formatApiErrorPayload(err) || 'Falha no login'
    throw new Error(String(text))
  }
  const data = (await res.json()) as { access_token: string }
  return data.access_token
}

export async function registerRequest(email: string, password: string): Promise<void> {
  const payload = {
    email: String(email ?? '')
      .trim()
      .toLowerCase(),
    password: String(password ?? ''),
  }
  const res = await fetch('/api/auth/register', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json; charset=utf-8' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    const text = formatApiErrorPayload(err) || 'Registo falhou'
    throw new Error(String(text))
  }
}

export type Conversation = {
  id: string
  title: string
  created_at: string
  updated_at: string
}

export type ChatMessage = {
  id: string
  role: string
  content: string
  created_at: string
}

export async function fetchConversations(token: string): Promise<Conversation[]> {
  const res = await fetch('/api/conversations', {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) throw new Error('Não foi possível carregar conversas')
  return res.json()
}

export async function createConversation(token: string): Promise<Conversation> {
  const res = await fetch('/api/conversations', {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({}),
  })
  if (!res.ok) throw new Error('Não foi possível criar conversa')
  return res.json()
}

export async function fetchMessages(token: string, conversationId: string): Promise<ChatMessage[]> {
  const res = await fetch(`/api/conversations/${conversationId}/messages`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) throw new Error('Não foi possível carregar mensagens')
  return res.json()
}

/**
 * Envia mensagem e invoca `onChunk` com texto acumulado conforme o stream chega.
 */
export async function streamAssistantReply(
  token: string,
  conversationId: string,
  content: string,
  onChunk: (accumulated: string) => void
): Promise<string> {
  const res = await fetch(`/api/conversations/${conversationId}/messages/stream`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ content }),
  })
  if (!res.ok) {
    const err = await res.text()
    throw new Error(err || 'Erro no agente')
  }
  const reader = res.body!.getReader()
  const dec = new TextDecoder()
  let acc = ''
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    acc += dec.decode(value, { stream: true })
    onChunk(acc)
  }
  return acc
}
