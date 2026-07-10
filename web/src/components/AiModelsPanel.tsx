/**
 * Painel administrativo de modelos IA — sincroniza catálogo OpenRouter para o
 * banco e mostra a lista resultante (com pricing). É a fonte que alimenta o
 * seletor de modelo no chat.
 */

import { useEffect, useMemo, useState } from 'react'
import {
  errorToUserMessage,
  fetchAiModels,
  syncAiModelsFromOpenrouter,
  type AiModel,
  type AiModelSyncResult,
} from '../api'
import styles from '../pages/settings.module.css'

const PAGE_SIZE = 25

/**
 * Formata um custo USD por 1M tokens. Retorna "free", "?? " ou "$0.15".
 */
function fmtCost(value: number | null): string {
  if (value == null) return '?? '
  if (value === 0) return 'free'
  if (value < 0.01) return `$${value.toFixed(4)}`
  return `$${value.toFixed(2)}`
}

export interface AiModelsPanelProps {
  token: string
  canManageCatalog?: boolean
}

export function AiModelsPanel({ token, canManageCatalog = false }: AiModelsPanelProps) {
  const [models, setModels] = useState<AiModel[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [syncing, setSyncing] = useState(false)
  const [syncResult, setSyncResult] = useState<AiModelSyncResult | null>(null)
  const [filter, setFilter] = useState('')
  const [page, setPage] = useState(0)

  useEffect(() => {
    void load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function load() {
    setLoading(true)
    setError(null)
    try {
      setModels(await fetchAiModels(token))
    } catch (err) {
      setError(errorToUserMessage(err))
    } finally {
      setLoading(false)
    }
  }

  async function handleSync() {
    setSyncing(true)
    setError(null)
    setSyncResult(null)
    try {
      const result = await syncAiModelsFromOpenrouter(token)
      setSyncResult(result)
      await load()
    } catch (err) {
      setError(errorToUserMessage(err))
    } finally {
      setSyncing(false)
    }
  }

  const filtered = useMemo(() => {
    const q = filter.trim().toLowerCase()
    const list = q
      ? models.filter(
          (m) =>
            m.model_id.toLowerCase().includes(q) ||
            m.display_name.toLowerCase().includes(q),
        )
      : models
    return [...list].sort((a, b) => {
      const ai = a.input_cost_per_1m_usd ?? Number.POSITIVE_INFINITY
      const bi = b.input_cost_per_1m_usd ?? Number.POSITIVE_INFINITY
      if (ai !== bi) return ai - bi
      return a.display_name.localeCompare(b.display_name)
    })
  }, [models, filter])

  const pages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE))
  const safePage = Math.min(page, pages - 1)
  const slice = filtered.slice(safePage * PAGE_SIZE, (safePage + 1) * PAGE_SIZE)

  return (
    <section className={styles.section}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.75rem' }}>
        <div>
          <h2 className={styles.sectionTitle}>Modelos IA</h2>
          <p className={styles.sectionDesc} style={{ marginTop: '0.25rem' }}>
            Catálogo de modelos disponíveis para escolha no chat. Faça sync com
            o OpenRouter para popular preços e novos modelos. Apenas super admin
            pode sincronizar e liberar modelos pagos.
          </p>
        </div>
        {canManageCatalog && (
          <button
            type="button"
            className={styles.primaryBtn}
            onClick={handleSync}
            disabled={syncing}
            aria-label="Sincronizar catálogo de modelos do OpenRouter"
            title="Buscar /api/v1/models do OpenRouter e atualizar pricing"
          >
            <span className={styles.icon} aria-hidden="true">
              {syncing ? 'hourglass_empty' : 'cloud_download'}
            </span>
            <span>{syncing ? 'Sincronizando…' : 'Sync OpenRouter'}</span>
          </button>
        )}
      </div>

      {error && <p className={styles.errorMsg}>{error}</p>}

      {syncResult && (
        <p className={styles.hint} style={{ marginTop: '0.5rem' }}>
          Sync OK · {syncResult.fetched} modelos no catálogo
          {' · '}
          <strong>{syncResult.created}</strong> novos
          {' · '}
          <strong>{syncResult.updated}</strong> atualizados
          {' · '}
          <strong>{syncResult.deactivated}</strong> desactivados
        </p>
      )}

      <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', margin: '0.75rem 0 0.5rem' }}>
        <input
          className={styles.input}
          placeholder="Filtrar por nome ou id (ex.: gpt-4o, claude, gemini)…"
          value={filter}
          onChange={(e) => {
            setFilter(e.target.value)
            setPage(0)
          }}
          style={{ flex: 1, maxWidth: 480 }}
        />
        <span className={styles.hint}>{filtered.length} de {models.length}</span>
      </div>

      {loading ? (
        <p className={styles.hint}>Carregando…</p>
      ) : models.length === 0 ? (
        <p className={styles.hint}>
          Nenhum modelo cadastrado. Clique em <strong>Sync OpenRouter</strong>.
        </p>
      ) : (
        <>
          <table className={styles.table}>
            <thead>
              <tr>
                <th>Modelo</th>
                <th>ID</th>
                <th style={{ textAlign: 'right' }}>Input / 1M</th>
                <th style={{ textAlign: 'right' }}>Output / 1M</th>
                <th style={{ textAlign: 'right' }}>Contexto</th>
                <th>Capabilities</th>
              </tr>
            </thead>
            <tbody>
              {slice.map((m) => (
                <tr key={m.id}>
                  <td>{m.display_name}</td>
                  <td><code style={{ fontSize: '0.78rem' }}>{m.model_id}</code></td>
                  <td style={{ textAlign: 'right', fontFamily: 'JetBrains Mono, monospace' }}>
                    {fmtCost(m.input_cost_per_1m_usd)}
                  </td>
                  <td style={{ textAlign: 'right', fontFamily: 'JetBrains Mono, monospace' }}>
                    {fmtCost(m.output_cost_per_1m_usd)}
                  </td>
                  <td style={{ textAlign: 'right' }}>{m.context_window.toLocaleString('pt-BR')}</td>
                  <td>{(m.capabilities ?? []).join(', ')}</td>
                </tr>
              ))}
            </tbody>
          </table>

          {pages > 1 && (
            <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '0.6rem', marginTop: '0.75rem' }}>
              <button
                type="button"
                className={styles.actionBtn}
                onClick={() => setPage((p) => Math.max(0, p - 1))}
                disabled={safePage === 0}
              >
                <span className={styles.icon}>chevron_left</span>
              </button>
              <span className={styles.hint}>{safePage + 1} / {pages}</span>
              <button
                type="button"
                className={styles.actionBtn}
                onClick={() => setPage((p) => Math.min(pages - 1, p + 1))}
                disabled={safePage >= pages - 1}
              >
                <span className={styles.icon}>chevron_right</span>
              </button>
            </div>
          )}
        </>
      )}
    </section>
  )
}
