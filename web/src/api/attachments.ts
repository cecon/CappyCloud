import { apiFetch } from './http'

// ── Attachments ──────────────────────────────────────────────────────────────

/**
 * Metadado de um anexo (imagem) carregado numa conversa.
 *
 * O campo {@link previewUrl} é um path relativo (sem host) que deve ser
 * concatenado com o base da API para servir a imagem; obriga `Authorization`
 * para download — use {@link fetchAttachmentBlobUrl} para obter um Object URL
 * pronto para `<img src=…>`.
 */
export interface Attachment {
  id: string
  conversation_id: string
  mime_type: string
  original_filename: string
  size_bytes: number
  kind: 'image' | 'text' | 'markdown' | 'log' | 'pdf' | 'docx' | string
  has_description: boolean
  processing_status: 'uploaded' | 'described' | 'indexed' | 'error' | string
  chunks_count: number
  processing_error: string | null
  vision_model_used: string | null
  uploaded_at: string
  preview_url: string
}

/**
 * Faz upload de imagem ou artefato de conversa. Imagens são descritas por
 * visão; textos/documentos são extraídos e indexados em chunks da conversa.
 */
export async function uploadAttachment(
  token: string,
  conversationId: string,
  file: File,
  signal?: AbortSignal,
): Promise<Attachment> {
  const fd = new FormData()
  fd.append('file', file, file.name)
  const res = await apiFetch(`/api/conversations/${conversationId}/attachments`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
    body: fd,
    signal,
  })
  if (!res.ok) {
    const err = await res.text().catch(() => '')
    throw new Error(err || `Falha no upload (HTTP ${res.status})`)
  }
  return (await res.json()) as Attachment
}

/**
 * Apaga um anexo (storage físico + registo no banco). 204 No Content em sucesso.
 */
export async function deleteAttachment(
  token: string,
  conversationId: string,
  attachmentId: string,
): Promise<void> {
  const res = await apiFetch(
    `/api/conversations/${conversationId}/attachments/${attachmentId}`,
    {
      method: 'DELETE',
      headers: { Authorization: `Bearer ${token}` },
    },
  )
  if (!res.ok && res.status !== 204) {
    throw new Error(`Falha ao remover anexo (HTTP ${res.status})`)
  }
}

/**
 * Faz GET autenticado da imagem e devolve um Object URL pronto para usar em
 * `<img src=…>`. **Lembrar de revogar com `URL.revokeObjectURL` no unmount**
 * para libertar memória.
 */
export async function fetchAttachmentBlobUrl(
  token: string,
  conversationId: string,
  attachmentId: string,
): Promise<string> {
  const res = await apiFetch(
    `/api/conversations/${conversationId}/attachments/${attachmentId}`,
    { headers: { Authorization: `Bearer ${token}` } },
  )
  if (!res.ok) {
    throw new Error(`Falha ao carregar preview (HTTP ${res.status})`)
  }
  const blob = await res.blob()
  return URL.createObjectURL(blob)
}
