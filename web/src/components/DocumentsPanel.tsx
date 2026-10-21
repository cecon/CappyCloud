import { useEffect, useState } from 'react'
import {
  createRepoDocument,
  deleteRepoDocument,
  fetchDocumentGraphSummary,
  fetchRepoDocuments,
  reindexRepoDocument,
  uploadRepoDocument,
  type DocumentGraphSummary,
  type RepoDocument,
} from '../api'
import styles from './DocumentsPanel.module.css'
import { DocumentsTable } from './documents-panel/DocumentsTable'

type Tab = 'url' | 'text' | 'upload'

interface Props {
  token: string
  repositoryId: string
  repositoryName: string
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
  const [graphSummary, setGraphSummary] = useState<DocumentGraphSummary | null>(null)

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
        if (!file) throw new Error('Selecione um arquivo de documentação')
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
    if (!confirm(`Remover "${doc.title}"?? Os chunks indexados também serão apagados.`)) return
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

  async function handleTestGraph(doc: RepoDocument) {
    setBusyId(doc.id)
    setError(null)
    try {
      setGraphSummary(await fetchDocumentGraphSummary(token, doc.id))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Erro ao testar graph')
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
        Documentos consultáveis pelo agente e pelo MCP. Use esta área para importar
        schema de banco, manuais, PDFs e planilhas ligados a este repositório.
      </p>

      {/* ── Lista ─────────────────────────────────────────────── */}
      {loading && <p className={styles.empty}>Carregando documentos…</p>}
      {error && <p className={styles.errorMsg}>{error}</p>}
      {!loading && docs.length === 0 && (
        <p className={styles.empty}>Nenhum documento ainda. Importe o Markdown do schema abaixo.</p>
      )}

      {docs.length > 0 && (
        <DocumentsTable
          docs={docs}
          busyId={busyId}
          onReindex={handleReindex}
          onTestGraph={handleTestGraph}
          onDelete={handleDelete}
        />
      )}

      {graphSummary && (
        <div className={styles.graphSummary}>
          <strong>Graph validado</strong>
          <span>
            {graphSummary.graph_nodes_count} nos, {graphSummary.graph_edges_count} relacoes.
          </span>
          {graphSummary.sample_tables.length > 0 && (
            <span>Tabelas: {graphSummary.sample_tables.join(', ')}</span>
          )}
        </div>
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
            Arquivo
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
                placeholder="Título (opcional — usa o nome do arquivo)"
                value={fileTitle}
                onChange={(e) => setFileTitle(e.target.value)}
              />
              <input
                type="file"
                accept=".md,.markdown,.txt,.pdf,.docx,.xlsx,.xlsm"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                required
              />
              <small style={{ color: 'rgba(255,255,255,0.5)', fontSize: '0.78rem' }}>
                Formatos aceitos: MD, Markdown, TXT, PDF, DOCX, XLSX e XLSM. Máx 25 MB.
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
