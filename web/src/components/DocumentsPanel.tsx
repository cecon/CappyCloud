import { useEffect, useState } from 'react'
import {
  createRepoDocument,
  deleteRepoDocument,
  fetchRepoDocuments,
  reindexRepoDocument,
  uploadRepoDocument,
  type RepoDocument,
} from '../api'
import styles from './DocumentsPanel.module.css'

type Tab = 'url' | 'text' | 'upload'

interface Props {
  token: string
  repositoryId: string
  repositoryName: string
}

const SOURCE_LABELS: Record<string, string> = {
  url: 'URL',
  text: 'Texto',
  pdf: 'PDF',
  xlsx: 'Excel',
}

function formatDate(iso: string | null): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (isNaN(d.getTime())) return '—'
  return d.toLocaleString('pt-BR', {
    day: '2-digit',
    month: '2-digit',
    year: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function DocumentsPanel({ token, repositoryId, repositoryName }: Props) {
  const [docs, setDocs] = useState<RepoDocument[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [tab, setTab] = useState<Tab>('url')
  const [submitting, setSubmitting] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)

  const [url, setUrl] = useState('')
  const [textTitle, setTextTitle] = useState('')
  const [textBody, setTextBody] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [fileTitle, setFileTitle] = useState('')

  const [busyId, setBusyId] = useState<string | null>(null)

  useEffect(() => {
    void load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [repositoryId])

  async function load() {
    setLoading(true)
    setError(null)
    try {
      setDocs(await fetchRepoDocuments(token, repositoryId))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Erro ao carregar documentos')
    } finally {
      setLoading(false)
    }
  }

  function resetForm() {
    setUrl('')
    setTextTitle('')
    setTextBody('')
    setFile(null)
    setFileTitle('')
    setFormError(null)
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setFormError(null)
    setSubmitting(true)
    try {
      let created: RepoDocument
      if (tab === 'url') {
        if (!url.trim()) throw new Error('URL é obrigatória')
        created = await createRepoDocument(token, repositoryId, {
          source_type: 'url',
          source_uri: url.trim(),
        })
      } else if (tab === 'text') {
        if (!textBody.trim()) throw new Error('Conteúdo é obrigatório')
        created = await createRepoDocument(token, repositoryId, {
          source_type: 'text',
          title: textTitle.trim() || null,
          content: textBody,
        })
      } else {
        if (!file) throw new Error('Selecione um ficheiro PDF ou XLSX')
        created = await uploadRepoDocument(
          token,
          repositoryId,
          file,
          fileTitle.trim() || null,
        )
      }
      setDocs((prev) => [created, ...prev])
      resetForm()
    } catch (e) {
      setFormError(e instanceof Error ? e.message : 'Erro desconhecido')
    } finally {
      setSubmitting(false)
    }
  }

  async function handleReindex(doc: RepoDocument) {
    setBusyId(doc.id)
    try {
      const updated = await reindexRepoDocument(token, doc.id)
      setDocs((prev) => prev.map((d) => (d.id === doc.id ? updated : d)))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Erro ao reindexar')
    } finally {
      setBusyId(null)
    }
  }

  async function handleDelete(doc: RepoDocument) {
    if (!confirm(`Remover "${doc.title}"? Os chunks indexados também serão apagados.`)) return
    setBusyId(doc.id)
    try {
      await deleteRepoDocument(token, doc.id)
      setDocs((prev) => prev.filter((d) => d.id !== doc.id))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Erro ao remover')
    } finally {
      setBusyId(null)
    }
  }

  return (
    <div className={styles.panel}>
      <div className={styles.panelHeader}>
        <h3 className={styles.panelTitle}>
          <span className={styles.icon}>menu_book</span>
          Documentos · {repositoryName}
        </h3>
      </div>
      <p className={styles.panelDesc}>
        Documentação de produto consultável pelo agente. Os chunks ficam disponíveis
        para todos os utilizadores que conversem sobre este repositório.
      </p>

      {/* ── Lista ─────────────────────────────────────────────── */}
      {loading && <p className={styles.empty}>Carregando documentos…</p>}
      {error && <p className={styles.errorMsg}>{error}</p>}
      {!loading && docs.length === 0 && (
        <p className={styles.empty}>Nenhum documento ainda. Adicione abaixo.</p>
      )}

      {docs.length > 0 && (
        <table className={styles.docsTable}>
          <thead>
            <tr>
              <th>Título</th>
              <th>Tipo</th>
              <th>Versão</th>
              <th>Chunks</th>
              <th>Status</th>
              <th>Indexado em</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {docs.map((d) => (
              <tr key={d.id}>
                <td className={styles.docTitle} title={d.title}>
                  {d.title}
                  {d.error_message && (
                    <div className={styles.errorMsg} style={{ fontSize: '0.75rem' }}>
                      {d.error_message}
                    </div>
                  )}
                </td>
                <td>{SOURCE_LABELS[d.source_type] ?? d.source_type}</td>
                <td>v{d.version}</td>
                <td>{d.chunks_count}</td>
                <td>
                  <span
                    className={`${styles.statusBadge} ${
                      styles[`status_${d.status}`] ?? ''
                    }`}
                  >
                    {d.status}
                  </span>
                </td>
                <td>{formatDate(d.indexed_at)}</td>
                <td style={{ whiteSpace: 'nowrap' }}>
                  {(d.source_type === 'url' || d.source_type === 'text') && (
                    <button
                      className={styles.iconBtn}
                      onClick={() => handleReindex(d)}
                      disabled={busyId === d.id}
                      title="Reindexar"
                    >
                      <span className={styles.icon}>
                        {busyId === d.id ? 'hourglass_empty' : 'refresh'}
                      </span>
                    </button>
                  )}
                  <button
                    className={`${styles.iconBtn} ${styles.iconBtnDanger}`}
                    onClick={() => handleDelete(d)}
                    disabled={busyId === d.id}
                    title="Remover"
                  >
                    <span className={styles.icon}>delete</span>
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {/* ── Form ──────────────────────────────────────────────── */}
      <div style={{ marginTop: '1rem' }}>
        <div className={styles.tabs}>
          <button
            type="button"
            className={`${styles.tab} ${tab === 'url' ? styles.tabActive : ''}`}
            onClick={() => {
              setTab('url')
              resetForm()
            }}
          >
            URL
          </button>
          <button
            type="button"
            className={`${styles.tab} ${tab === 'text' ? styles.tabActive : ''}`}
            onClick={() => {
              setTab('text')
              resetForm()
            }}
          >
            Texto / FAQ
          </button>
          <button
            type="button"
            className={`${styles.tab} ${tab === 'upload' ? styles.tabActive : ''}`}
            onClick={() => {
              setTab('upload')
              resetForm()
            }}
          >
            PDF / Excel
          </button>
        </div>

        <form onSubmit={handleSubmit} className={styles.formGrid}>
          {tab === 'url' && (
            <input
              type="url"
              placeholder="https://docs.exemplo.com/produto/..."
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              required
            />
          )}

          {tab === 'text' && (
            <>
              <input
                type="text"
                placeholder="Título (opcional)"
                value={textTitle}
                onChange={(e) => setTextTitle(e.target.value)}
              />
              <textarea
                placeholder="Cole aqui texto, perguntas/respostas, instruções…"
                value={textBody}
                onChange={(e) => setTextBody(e.target.value)}
                required
              />
            </>
          )}

          {tab === 'upload' && (
            <>
              <input
                type="text"
                placeholder="Título (opcional — usa o nome do ficheiro)"
                value={fileTitle}
                onChange={(e) => setFileTitle(e.target.value)}
              />
              <input
                type="file"
                accept=".pdf,.xlsx,.xlsm"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                required
              />
              <small style={{ color: 'rgba(255,255,255,0.5)', fontSize: '0.78rem' }}>
                Formatos aceitos: PDF, XLSX, XLSM. Máx 25 MB.
              </small>
            </>
          )}

          {formError && <p className={styles.errorMsg}>{formError}</p>}
          <div className={styles.formActions}>
            <button className={styles.submitBtn} type="submit" disabled={submitting}>
              {submitting ? 'Processando…' : 'Adicionar documento'}
            </button>
            {submitting && (
              <small style={{ color: 'rgba(255,255,255,0.55)', fontSize: '0.78rem' }}>
                Extração e embeddings podem demorar segundos…
              </small>
            )}
          </div>
        </form>
      </div>
    </div>
  )
}
