import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  AuthError,
  createRepository,
  deleteRepository,
  fetchBranchesFromUrl,
  fetchRepositories,
  fetchSandboxes,
  getToken,
  setToken,
  syncRepository,
  updateRepository,
  type Repository,
  type RepositoryCreate,
  type Sandbox,
} from '../api'
import styles from './settings.module.css'

const PROVIDER_TYPES: Array<{ value: string; label: string }> = [
  { value: 'azure_devops', label: 'Azure DevOps' },
  { value: 'github', label: 'GitHub' },
  { value: 'gitlab', label: 'GitLab' },
  { value: 'bitbucket', label: 'Bitbucket' },
]

const EMPTY_REPO_FORM: RepositoryCreate = {
  slug: '',
  name: '',
  clone_url: '',
  default_branch: 'main',
  provider_id: null,
  sandbox_id: null,
  pat_token: '',
  provider_type: null,
}

/**
 * Página de configurações: gerencia repositórios disponíveis no chat.
 * O PAT é cadastrado inline em cada repositório (cria provider implícito no backend).
 */
export function SettingsPage() {
  const token = getToken()!

  const [repos, setRepos] = useState<Repository[]>([])
  const [sandboxes, setSandboxes] = useState<Sandbox[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [repoForm, setRepoForm] = useState<RepositoryCreate>(EMPTY_REPO_FORM)
  const [editingRepoId, setEditingRepoId] = useState<string | null>(null)
  const [repoFormError, setRepoFormError] = useState<string | null>(null)
  const [savingRepo, setSavingRepo] = useState(false)
  const [availableBranches, setAvailableBranches] = useState<string[]>([])
  const [loadingBranches, setLoadingBranches] = useState(false)
  const [syncingId, setSyncingId] = useState<string | null>(null)
  const [deletingId, setDeletingId] = useState<string | null>(null)

  useEffect(() => {
    void loadAll()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function loadAll() {
    setLoading(true)
    setError(null)
    try {
      const [repoList, sandboxList] = await Promise.all([
        fetchRepositories(token),
        fetchSandboxes(token),
      ])
      setRepos(repoList)
      setSandboxes(sandboxList)
      if (sandboxList.length > 0) {
        setRepoForm((prev) =>
          prev.sandbox_id ? prev : { ...prev, sandbox_id: sandboxList[0].id },
        )
      }
    } catch (err) {
      if (err instanceof AuthError) {
        setToken(null)
        window.location.href = '/login'
        return
      }
      setError(err instanceof Error ? err.message : 'Não foi possível carregar dados.')
    } finally {
      setLoading(false)
    }
  }

  function resetForm() {
    setRepoForm({ ...EMPTY_REPO_FORM, sandbox_id: sandboxes[0]?.id ?? null })
    setEditingRepoId(null)
    setAvailableBranches([])
    setRepoFormError(null)
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault()
    setRepoFormError(null)
    setSavingRepo(true)
    try {
      if (editingRepoId) {
        const updated = await updateRepository(token, editingRepoId, repoForm)
        setRepos((prev) => prev.map((r) => (r.id === editingRepoId ? updated : r)))
      } else {
        const created = await createRepository(token, repoForm)
        setRepos((prev) => [...prev, created])
      }
      resetForm()
    } catch (err) {
      setRepoFormError(err instanceof Error ? err.message : 'Erro desconhecido')
    } finally {
      setSavingRepo(false)
    }
  }

  function handleEdit(r: Repository) {
    setEditingRepoId(r.id)
    setRepoForm({
      slug: r.slug,
      name: r.name,
      clone_url: r.clone_url,
      default_branch: r.default_branch,
      provider_id: r.provider_id ?? null,
      sandbox_id: r.sandbox_id ?? sandboxes[0]?.id ?? null,
      pat_token: '',
      provider_type: null,
    })
    setAvailableBranches([])
    setRepoFormError(null)
    window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' })
  }

  async function handleLoadBranches() {
    if (!repoForm.clone_url) return
    setLoadingBranches(true)
    try {
      const result = await fetchBranchesFromUrl(token, repoForm.clone_url)
      setAvailableBranches(result.branches)
      setRepoForm((prev) => ({ ...prev, default_branch: result.default }))
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
      await loadAll()
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

  function set<K extends keyof RepositoryCreate>(field: K, value: RepositoryCreate[K]) {
    setRepoForm((prev) => ({ ...prev, [field]: value }))
  }

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <Link to="/" className={styles.backLink}>
          <span className={styles.icon}>arrow_back</span>
          Voltar ao chat
        </Link>
        <h1 className={styles.title}>Configurações</h1>
        <div style={{ marginTop: '0.5rem', fontSize: '0.85rem', display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
          <Link to="/agents" className={styles.backLink}>
            <span className={styles.icon}>support_agent</span>
            Agentes →
          </Link>
          <Link to="/skills" className={styles.backLink}>
            <span className={styles.icon}>menu_book</span>
            Skills →
          </Link>
        </div>
      </header>

      {/* ── Lista ─────────────────────────────────────────────── */}
      <section className={styles.section}>
        <h2 className={styles.sectionTitle}>Repositórios</h2>
        <p className={styles.sectionDesc}>
          Repositórios disponíveis para seleção no chat. O PAT (token de acesso) é
          guardado encriptado e propagado ao sandbox automaticamente.
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
                    <span
                      className={`${styles.badge} ${styles[`badge_${r.sandbox_status}`] ?? ''}`}
                    >
                      {r.sandbox_status}
                    </span>
                  </td>
                  <td className={styles.actions}>
                    <button
                      className={styles.actionBtn}
                      onClick={() => handleEdit(r)}
                      title="Editar"
                    >
                      <span className={styles.icon}>edit</span>
                    </button>
                    <button
                      className={styles.actionBtn}
                      onClick={() => handleSync(r.id)}
                      disabled={syncingId === r.id}
                      title="Sincronizar (clone/fetch) no sandbox"
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

      {/* ── Form ──────────────────────────────────────────────── */}
      <section className={styles.section}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h2 className={styles.sectionTitle}>
            {editingRepoId ? 'Editar repositório' : 'Adicionar repositório'}
          </h2>
          {editingRepoId && (
            <button
              type="button"
              className={styles.actionBtn}
              onClick={resetForm}
              title="Cancelar edição"
            >
              <span className={styles.icon}>close</span>
            </button>
          )}
        </div>

        <form onSubmit={handleSave} className={styles.form}>
          <div className={styles.formRow}>
            <label className={styles.label}>
              Nome
              <input
                className={styles.input}
                value={repoForm.name}
                onChange={(e) => set('name', e.target.value)}
                placeholder="Meu Projeto"
                required
              />
            </label>
            <label className={styles.label}>
              Slug
              <input
                className={styles.input}
                value={repoForm.slug}
                onChange={(e) => set('slug', e.target.value)}
                placeholder="meu-projeto"
                required
              />
            </label>
          </div>

          <label className={styles.label}>
            URL de clone
            <input
              className={styles.input}
              value={repoForm.clone_url}
              onChange={(e) => set('clone_url', e.target.value)}
              placeholder="https://dev.azure.com/org/proj/_git/repo"
              required
            />
          </label>

          <div className={styles.formRow}>
            <label className={styles.label}>
              Tipo do repositório
              <select
                className={styles.input}
                value={repoForm.provider_type ?? ''}
                onChange={(e) => set('provider_type', e.target.value || null)}
              >
                <option value="">— inferir pela URL —</option>
                {PROVIDER_TYPES.map((t) => (
                  <option key={t.value} value={t.value}>
                    {t.label}
                  </option>
                ))}
              </select>
            </label>
            <label className={styles.label} style={{ flex: 2 }}>
              Personal Access Token (PAT)
              <input
                type="password"
                className={styles.input}
                value={repoForm.pat_token ?? ''}
                onChange={(e) => set('pat_token', e.target.value || null)}
                placeholder={
                  editingRepoId
                    ? 'Deixe vazio para manter o token atual'
                    : 'Cole o PAT (deixe vazio para repos públicos)'
                }
                autoComplete="new-password"
              />
            </label>
          </div>

          <div className={styles.branchRow}>
            <label className={styles.label} style={{ flex: 1 }}>
              Branch padrão
              {availableBranches.length > 0 ? (
                <select
                  className={styles.input}
                  value={repoForm.default_branch}
                  onChange={(e) => set('default_branch', e.target.value)}
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
                  value={repoForm.default_branch}
                  onChange={(e) => set('default_branch', e.target.value)}
                  placeholder="main"
                  required
                />
              )}
            </label>
            <button
              type="button"
              className={styles.reloadBranchBtn}
              onClick={handleLoadBranches}
              disabled={!repoForm.clone_url || loadingBranches}
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
              value={repoForm.sandbox_id ?? ''}
              onChange={(e) => set('sandbox_id', e.target.value || null)}
              required={sandboxes.length > 0}
            >
              {sandboxes.length === 0 && <option value="">Nenhuma sandbox disponível</option>}
              {sandboxes.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                  {s.status !== 'active' ? ` (${s.status})` : ''}
                </option>
              ))}
            </select>
          </label>

          {repoFormError && <p className={styles.errorMsg}>{repoFormError}</p>}
          <button className={styles.submitBtn} type="submit" disabled={savingRepo}>
            {savingRepo ? 'Salvando…' : editingRepoId ? 'Salvar alterações' : 'Adicionar'}
          </button>
        </form>
      </section>
    </div>
  )
}
