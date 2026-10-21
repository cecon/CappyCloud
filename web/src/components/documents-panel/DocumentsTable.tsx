import type { RepoDocument } from '../../api'
import styles from '../DocumentsPanel.module.css'

const SOURCE_LABELS: Record<string, string> = {
  url: 'URL',
  text: 'Texto',
  markdown: 'Markdown',
  txt: 'TXT',
  pdf: 'PDF',
  xlsx: 'Excel',
  docx: 'Word',
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

interface DocumentsTableProps {
  docs: RepoDocument[]
  busyId: string | null
  onReindex: (doc: RepoDocument) => void
  onTestGraph: (doc: RepoDocument) => void
  onDelete: (doc: RepoDocument) => void
}

export function DocumentsTable({ docs, busyId, onReindex, onTestGraph, onDelete }: DocumentsTableProps) {
  return (
    <table className={styles.docsTable}>
      <thead>
        <tr>
          <th>Título</th>
          <th>Tipo</th>
          <th>Versão</th>
          <th>Chunks</th>
          <th>Graph</th>
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
                className={`${styles.graphBadge} ${
                  d.graph_nodes_count > 0 ? styles.graphReady : styles.graphEmpty
                }`}
                title={
                  d.graph_nodes_count > 0
                    ? `${d.graph_nodes_count} nos e ${d.graph_edges_count} relacoes mapeadas`
                    : 'Documento sem graph mapeado'
                }
              >
                {d.graph_nodes_count > 0 ? `${d.graph_nodes_count} nos` : 'sem graph'}
              </span>
            </td>
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
                  onClick={() => onReindex(d)}
                  disabled={busyId === d.id}
                  title="Reindexar"
                >
                  <span className={styles.icon}>
                    {busyId === d.id ? 'hourglass_empty' : 'refresh'}
                  </span>
                </button>
              )}
              {d.graph_nodes_count > 0 && (
                <button
                  className={styles.iconBtn}
                  onClick={() => onTestGraph(d)}
                  disabled={busyId === d.id}
                  title="Testar graph"
                >
                  <span className={styles.icon}>hub</span>
                </button>
              )}
              <button
                className={`${styles.iconBtn} ${styles.iconBtnDanger}`}
                onClick={() => onDelete(d)}
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
  )
}
