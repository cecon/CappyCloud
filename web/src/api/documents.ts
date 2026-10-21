import { apiFetch, formatApiErrorPayload } from './http'

// ── Documents (RAG por repositório) ──────────────────────────────────────────

export type DocumentSourceType = 'pdf' | 'xlsx' | 'url' | 'text' | 'markdown' | 'txt' | 'docx'

export interface RepoDocument {
  id: string
  repository_id: string
  source_type: DocumentSourceType | string
  source_uri: string
  title: string
  version: number
  checksum: string | null
  status: 'pending' | 'processing' | 'indexed' | 'error' | string
  error_message: string | null
  chunks_count: number
  graph_nodes_count: number
  graph_edges_count: number
  created_at: string
  updated_at: string
  indexed_at: string | null
}

export interface DocumentGraphSummary {
  document_id: string
  graph_nodes_count: number
  graph_edges_count: number
  sample_tables: string[]
}

export interface DocumentCreate {
  source_type: DocumentSourceType
  source_uri?: string
  title?: string | null
  /** Conteúdo bruto — obrigatório quando source_type='text'. */
  content?: string | null
}

export async function fetchRepoDocuments(
  token: string,
  repoId: string,
): Promise<RepoDocument[]> {
  const res = await apiFetch(`/api/repositories/${repoId}/documents`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) return []
  return res.json()
}

export async function createRepoDocument(
  token: string,
  repoId: string,
  data: DocumentCreate,
): Promise<RepoDocument> {
  const res = await apiFetch(`/api/repositories/${repoId}/documents`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || 'Falha ao criar documento')
  }
  return res.json()
}

export async function uploadRepoDocument(
  token: string,
  repoId: string,
  file: File,
  title: string | null = null,
): Promise<RepoDocument> {
  const form = new FormData()
  form.append('file', file)
  if (title) form.append('title', title)
  const res = await apiFetch(`/api/repositories/${repoId}/documents/upload`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
    body: form,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || 'Falha ao enviar ficheiro')
  }
  return res.json()
}

export async function reindexRepoDocument(
  token: string,
  docId: string,
): Promise<RepoDocument> {
  const res = await apiFetch(`/api/documents/${docId}/reindex`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || 'Falha ao reindexar')
  }
  return res.json()
}

export async function fetchDocumentGraphSummary(
  token: string,
  docId: string,
): Promise<DocumentGraphSummary> {
  const res = await apiFetch(`/api/documents/${docId}/graph-summary`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || 'Falha ao testar graph do documento')
  }
  return res.json()
}


export async function deleteRepoDocument(token: string, docId: string): Promise<void> {
  const res = await apiFetch(`/api/documents/${docId}`, {
    method: 'DELETE',
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) throw new Error('Falha ao remover documento')
}
