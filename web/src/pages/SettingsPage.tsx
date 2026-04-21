import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  createRepository,
  deleteRepository,
  fetchBranchesFromUrl,
  fetchRepositories,
  fetchSandboxes,
  getToken,
  syncRepository,
  type Repository,
  type RepositoryCreate,
  type Sandbox,
} from '../api'
import styles from './settings.module.css'

const EMPTY_FORM: RepositoryCreate = {
  slug: '',
  name: '',
  clone_url: '',
  default_branch: 'main',
  sandbox_id: null,
}

/**
 * Página de configurações: gerencia repositórios disponíveis no chat.
 */
export function SettingsPage() {
  const token = getToken()!

  const [repos, setRepos] = useState<Repository[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [sandboxes, setSandboxes] = useState<Sandbox[]>([])

  const [form, setForm] = useState<RepositoryCreate>(EMPTY_FORM)
  const [formError, setFormError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  const [availableBranches, setAvailableBranches] = useState<string[]>([])
  const [loadingBranches, setLoadingBranches] = useState(false)

  const [syncingId, setSyncingId] = useState<string | null>(null)
  const [deletingId, setDeletingId] = useState<string | null>(null)

  useEffect(() => {
    loadRepos()
    fetchSandboxes(token).then((list) => {
      setSandboxes(list)
      if (list.length > 0) {
        setForm((prev) => ({ ...prev, sandbox_id: list[0].id }))
      }
    })
  }, [])

  async function loadRepos() {
    setLoading(true)
    setError(null)
    try {
      setRepos(await fetchRepositories(token))
    } catch {
      setError('Não foi possível carregar os repositórios.')
    } finally {
      setLoading(false)
    }
  }

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault()
    setFormError(null)
    setSaving(true)
    try {
      const created = await createRepository(token, form)
      setRepos((prev) => [...prev, created])
      setForm({ ...EMPTY_FORM, sandbox_id: sandboxes[0]?.id ?? null })
      setAvailableBranches([])
    } catch (err) {
      setFormError(err instanceof Error ? err.message : 'Erro desconhecido')
    } finally {
      setSaving(false)
    }
  }

  async function handleLoadBranches() {
    if (!form.clone_url) return
    setLoadingBranches(true)
    try {
      const result = await fetchBranchesFromUrl(token, form.clone_url)
      setAvailableBranches(result.branches)
      setForm((prev) => ({ ...prev, default_branch: result.default }))
    } finally {
      setLoadingBranches(false)
    }
  }

  async function handleSync(id: string) {
    setSyncingId(id)
    try {
      await syncRepository(token, id)
    } finally {
      setSyncingId(null)
      await loadRepos()
    }
  }

  async function handleDelete(id: string) {
    if (!confirm('Remover este repositório?')) return
    setDeletingId(id)
    try {
      await deleteRepository(token, id)
      setRepos((prev) => prev.filter((r) => r.id !== id))
    } finally {
      setDeletingId(null)
    }
  }

  function handleFormChange(field: keyof RepositoryCreate, value: string | null) {
    setForm((prev) => ({ ...prev, [field]: value }))
  }

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <Link to="/" className={styles.backLink}>
          <span className={styles.icon}>arrow_back</span>
          Voltar ao chat
        </Link>
        <h1 className={styles.title}>Configurações</h1>
      </header>

      <section className={styles.section}>
        <h2 className={styles.sectionTitle}>Repositórios</h2>
        <p className={styles.sectionDesc}>
          Repositórios cadastrados aqui ficam disponíveis para seleção no chat.
        </p>

        {loading && <p className={styles.hint}>Carregando…</p>}
        {error && <p className={styles.errorMsg}>{error}</p>}

        {!loading && repos.length === 0 && (
          <p className={styles.hint}>Nenhum repositório cadastrado ainda.</p>
        )}

        {repos.length > 0 && (
          <table className={styles.table}>
            <thead>
              <tr>
                <th>Nome</th>
                <th>Slug</th>
                <th>URL de clone</th>
                <th>Branch</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {repos.map((r) => (
                <tr key={r.id}>
                  <td>{r.name}</td>
                  <td>
                    <code>{r.slug}</code>
                  </td>
                  <td className={styles.urlCell} title={r.clone_url}>
                    {r.clone_url}
                  </td>
                  <td>{r.default_branch}</td>
                  <td>
                    <span className={`${styles.badge} ${styles[`badge_${r.sandbox_status}`] ?? ''}`}>
                      {r.sandbox_status}
                    </span>
                  </td>
                  <td className={styles.actions}>
                    <button
                      className={styles.actionBtn}
                      onClick={() => handleSync(r.id)}
                      disabled={syncingId === r.id}
                      title="Sincronizar no sandbox"
                    >
                      <span className={styles.icon}>
                        {syncingId === r.id ? 'hourglass_empty' : 'sync'}
                      </span>
                    </button>
                    <button
                      className={`${styles.actionBtn} ${styles.actionBtnDanger}`}
                      onClick={() => handleDelete(r.id)}
                      disabled={deletingId === r.id}
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
      </section>

      <section className={styles.section}>
        <h2 className={styles.sectionTitle}>Adicionar repositório</h2>
        <form onSubmit={handleAdd} className={styles.form}>
          <div className={styles.formRow}>
            <label className={styles.label}>
              Nome
              <input
                className={styles.input}
                value={form.name}
                onChange={(e) => handleFormChange('name', e.target.value)}
                placeholder="Meu Projeto"
                required
              />
            </label>
            <label className={styles.label}>
              Slug
              <input
                className={styles.input}
                value={form.slug}
                onChange={(e) => handleFormChange('slug', e.target.value)}
                placeholder="meu-projeto"
                required
              />
            </label>
          </div>
          <label className={styles.label}>
            URL de clone
            <input
              className={styles.input}
              value={form.clone_url}
              onChange={(e) => handleFormChange('clone_url', e.target.value)}
              placeholder="https://github.com/org/repo.git"
              required
            />
          </label>
          <div className={styles.branchRow}>
            <label className={styles.label} style={{ flex: 1 }}>
              Branch padrão
              {availableBranches.length > 0 ? (
                <select
                  className={styles.input}
                  value={form.default_branch}
                  onChange={(e) => handleFormChange('default_branch', e.target.value)}
                  required
                >
                  {availableBranches.map((b) => (
                    <option key={b} value={b}>
                      {b}
                    </option>
                  ))}
                </select>
              ) : (
                <input
                  className={styles.input}
                  value={form.default_branch}
                  onChange={(e) => handleFormChange('default_branch', e.target.value)}
                  placeholder="main"
                  required
                />
              )}
            </label>
            <button
              type="button"
              className={styles.reloadBranchBtn}
              onClick={handleLoadBranches}
              disabled={!form.clone_url || loadingBranches}
              title="Carregar branches da URL"
            >
              <span className={`${styles.icon} ${loadingBranches ? styles.spinning : ''}`}>
                sync
              </span>
            </button>
          </div>
          <label className={styles.label}>
            Sandbox
            <select
              className={styles.input}
              value={form.sandbox_id ?? ''}
              onChange={(e) => handleFormChange('sandbox_id', e.target.value || null)}
              required={sandboxes.length > 0}
            >
              {sandboxes.length === 0 && (
                <option value="">Nenhuma sandbox disponível</option>
              )}
              {sandboxes.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                  {s.status !== 'active' ? ` (${s.status})` : ''}
                </option>
              ))}
            </select>
          </label>
          {formError && <p className={styles.errorMsg}>{formError}</p>}
          <button className={styles.submitBtn} type="submit" disabled={saving}>
            {saving ? 'Salvando…' : 'Adicionar'}
          </button>
        </form>
      </section>
    </div>
  )
}
