import type { Attachment } from './attachments'
import { apiFetch, formatApiErrorPayload } from './http'
import type { ConversationActivityTurn } from './streamTypes'

// -- Admin · Conversa como o usuário viu (passos e anexos) -------------------

/** Anexo de uma conversa visto pelo admin, já ligado à pergunta em que foi enviado. */
export interface AdminConversationAttachment extends Attachment {
  message_id: string | null
}

async function adminGet(token: string, path: string, fallback: string): Promise<Response> {
  const res = await apiFetch(`/api/admin/conversations/${path}`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || fallback)
  }
  return res
}

/** Passos do agente por turno, no mesmo formato do chat. */
export async function fetchAdminConversationActivity(
  token: string,
  conversationId: string,
): Promise<ConversationActivityTurn[]> {
  const res = await adminGet(
    token,
    `${encodeURIComponent(conversationId)}/activity`,
    'Falha ao carregar os passos do agente',
  )
  return res.json()
}

export async function fetchAdminConversationAttachments(
  token: string,
  conversationId: string,
): Promise<AdminConversationAttachment[]> {
  const res = await adminGet(
    token,
    `${encodeURIComponent(conversationId)}/attachments`,
    'Falha ao carregar os anexos',
  )
  return res.json()
}

/** Object URL do arquivo do anexo; revogar com `URL.revokeObjectURL` ao desmontar. */
export async function fetchAdminAttachmentBlobUrl(
  token: string,
  conversationId: string,
  attachmentId: string,
): Promise<string> {
  const res = await adminGet(
    token,
    `${encodeURIComponent(conversationId)}/attachments/${encodeURIComponent(attachmentId)}`,
    'Falha ao carregar o anexo',
  )
  return URL.createObjectURL(await res.blob())
}
