import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  AuthError,
  createAgent,
  createSkill,
  deleteAgent,
  deleteSkill,
  fetchAgents,
  fetchSkills,
  getToken,
  importSkillFromUrl,
  setToken,
  updateAgent,
  updateSkill,
  type Agent,
  type AgentCreate,
  type Skill,
  type SkillCreate,
} from '../api'
import styles from './settings.module.css'

const EMPTY_AGENT: AgentCreate = {
  slug: '',
  name: '',
  description: '',
  icon: 'support_agent',
  system_prompt: '',
  default_model: null,
  active: true,
}

const EMPTY_SKILL: SkillCreate = {
  agent_id: null,
  title: '',
  summary: '',
  content: '',
  tags: [],
  source_url: null,
}

/**
 * Página de gestão de Agentes (perfis com system_prompt) e Skills (knowledge base).
 * O agente selecionado tem as suas skills geridas inline.
 */
export function AgentsPage() {
  const token = getToken()!

  const [agents, setAgents] = useState<Agent[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [editingAgentId, setEditingAgentId] = useState<string | null>(null)
  const [agentForm, setAgentForm] = useState<AgentCreate>(EMPTY_AGENT)
  const [savingAgent, setSavingAgent] = useState(false)
  const [agentFormError, setAgentFormError] = useState<string | null>(null)

  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null)
  const [skills, setSkills] = useState<Skill[]>([])
  const [skillForm, setSkillForm] = useState<SkillCreate>(EMPTY_SKILL)
  const [savingSkill, setSavingSkill] = useState(false)
  const [skillFormError, setSkillFormError] = useState<string | null>(null)

  const [importUrl, setImportUrl] = useState('')
  const [importing, setImporting] = useState(false)
  const [importError, setImportError] = useState<string | null>(null)

  useEffect(() => {
    void loadAgents()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (selectedAgentId) void loadSkills(selectedAgentId)
    else setSkills([])
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedAgentId])

  async function loadAgents() {
    setLoading(true)
    setError(null)
    try {
      const list = await fetchAgents(token)
      setAgents(list)
      if (!selectedAgentId && list.length > 0) {
        setSelectedAgentId(list[0].id)
      }
    } catch (err) {
      if (err instanceof AuthError) {
        setToken(null)
        window.location.href = '/login'
        return
      }
      setError(err instanceof Error ? err.message : 'Erro ao carregar agentes')
    } finally {
      setLoading(false)
    }
  }

  async function loadSkills(agentId: string) {
    try {
      const list = await fetchSkills(token, agentId)
      setSkills(list)
    } catch (err) {
      if (err instanceof AuthError) {
        setToken(null)
        window.location.href = '/login'
      }
    }
  }

  function startEditAgent(a: Agent) {
    setEditingAgentId(a.id)
    setAgentForm({
      slug: a.slug,
      name: a.name,
      description: a.description,
      icon: a.icon,
      system_prompt: a.system_prompt,
      default_model: a.default_model,
      active: a.active,
    })
    setAgentFormError(null)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  function resetAgentForm() {
    setEditingAgentId(null)
    setAgentForm(EMPTY_AGENT)
    setAgentFormError(null)
  }

  async function handleSaveAgent(e: React.FormEvent) {
    e.preventDefault()
    setSavingAgent(true)
    setAgentFormError(null)
    try {
      if (editingAgentId) {
        const { slug, ...rest } = agentForm
        void slug
        const updated = await updateAgent(token, editingAgentId, rest)
        setAgents((prev) => prev.map((a) => (a.id === editingAgentId ? updated : a)))
      } else {
        const created = await createAgent(token, agentForm)
        setAgents((prev) => [...prev, created])
        setSelectedAgentId(created.id)
      }
      resetAgentForm()
    } catch (err) {
      setAgentFormError(err instanceof Error ? err.message : 'Erro desconhecido')
    } finally {
      setSavingAgent(false)
    }
  }

  async function handleDeleteAgent(id: string) {
    if (!confirm('Remover este agente e todas as suas skills?')) return
    try {
      await deleteAgent(token, id)
      setAgents((prev) => prev.filter((a) => a.id !== id))
      if (selectedAgentId === id) setSelectedAgentId(null)
      if (editingAgentId === id) resetAgentForm()
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Erro ao remover agente')
    }
  }

  async function handleSaveSkill(e: React.FormEvent) {
    e.preventDefault()
    if (!selectedAgentId) return
    setSavingSkill(true)
    setSkillFormError(null)
    try {
      const created = await createSkill(token, {
        ...skillForm,
        agent_id: selectedAgentId,
      })
      setSkills((prev) => [...prev, created])
      setSkillForm(EMPTY_SKILL)
    } catch (err) {
      setSkillFormError(err instanceof Error ? err.message : 'Erro desconhecido')
    } finally {
      setSavingSkill(false)
    }
  }

  async function handleDeleteSkill(id: string) {
    if (!confirm('Remover esta skill?')) return
    try {
      await deleteSkill(token, id)
      setSkills((prev) => prev.filter((s) => s.id !== id))
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Erro ao remover skill')
    }
  }

  async function handleToggleSkillActive(s: Skill) {
    try {
      const updated = await updateSkill(token, s.id, { active: !s.active })
      setSkills((prev) => prev.map((x) => (x.id === s.id ? updated : x)))
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Erro ao alternar skill')
    }
  }

  async function handleImportUrl(e: React.FormEvent) {
    e.preventDefault()
    if (!selectedAgentId || !importUrl) return
    setImporting(true)
    setImportError(null)
    try {
      const created = await importSkillFromUrl(token, importUrl, selectedAgentId)
      setSkills((prev) => [...prev, created])
      setImportUrl('')
    } catch (err) {
      setImportError(err instanceof Error ? err.message : 'Erro desconhecido')
    } finally {
      setImporting(false)
    }
  }

  const selectedAgent = agents.find((a) => a.id === selectedAgentId) ?? null

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <Link to="/" className={styles.backLink}>
          <span className={styles.icon}>arrow_back</span>
          Voltar ao chat
        </Link>
        <h1 className={styles.title}>Agentes</h1>
      </header>

      {/* ── Form criar/editar agente ───────────────────────────── */}
      <section className={styles.section}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h2 className={styles.sectionTitle}>
            {editingAgentId ? 'Editar agente' : 'Criar agente'}
          </h2>
          {editingAgentId && (
            <button type="button" className={styles.actionBtn} onClick={resetAgentForm}>
              <span className={styles.icon}>close</span>
            </button>
          )}
        </div>
        <p className={styles.sectionDesc}>
          Cada agente tem um <strong>system prompt</strong> que define o seu papel
          (ex.: "Dev RC AutoSystem"). Skills (knowledge base) podem ser anexadas
          abaixo, e o LLM consulta-as automaticamente quando relevantes.
        </p>

        <form onSubmit={handleSaveAgent} className={styles.form}>
          <div className={styles.formRow}>
            <label className={styles.label}>
              Nome
              <input
                className={styles.input}
                value={agentForm.name}
                onChange={(e) => setAgentForm((p) => ({ ...p, name: e.target.value }))}
                placeholder="Ex.: Dev RC AutoSystem"
                required
              />
            </label>
            <label className={styles.label}>
              Slug
              <input
                className={styles.input}
                value={agentForm.slug}
                onChange={(e) => setAgentForm((p) => ({ ...p, slug: e.target.value }))}
                placeholder="dev-rc-autosystem"
                pattern="^[a-z0-9][a-z0-9-]*$"
                required
                disabled={!!editingAgentId}
                title={editingAgentId ? 'Slug não pode mudar' : ''}
              />
            </label>
          </div>
          <label className={styles.label}>
            Descrição (opcional, para distinguir na UI)
            <input
              className={styles.input}
              value={agentForm.description ?? ''}
              onChange={(e) => setAgentForm((p) => ({ ...p, description: e.target.value }))}
              placeholder="Ajuda o time de suporte com dúvidas técnicas do AutoSystem"
            />
          </label>
          <label className={styles.label}>
            System prompt (markdown)
            <textarea
              className={styles.input}
              value={agentForm.system_prompt ?? ''}
              onChange={(e) =>
                setAgentForm((p) => ({ ...p, system_prompt: e.target.value }))
              }
              placeholder={`# Quem és tu\n\nÉs um Desenvolvedor especializado em ...\n\n# Como respondes\n- Em português\n- Curto e direto`}
              rows={10}
              style={{ fontFamily: 'monospace', resize: 'vertical' }}
              required
            />
          </label>
          {agentFormError && <p className={styles.errorMsg}>{agentFormError}</p>}
          <button className={styles.submitBtn} type="submit" disabled={savingAgent}>
            {savingAgent ? 'Salvando…' : editingAgentId ? 'Salvar alterações' : 'Criar agente'}
          </button>
        </form>
      </section>

      {/* ── Lista de agentes ───────────────────────────────────── */}
      <section className={styles.section}>
        <h2 className={styles.sectionTitle}>Agentes cadastrados</h2>
        {loading && <p className={styles.hint}>Carregando…</p>}
        {error && <p className={styles.errorMsg}>{error}</p>}
        {!loading && agents.length === 0 && (
          <p className={styles.hint}>Nenhum agente ainda.</p>
        )}
        {agents.length > 0 && (
          <table className={styles.table}>
            <thead>
              <tr>
                <th></th>
                <th>Nome</th>
                <th>Slug</th>
                <th>Skills</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {agents.map((a) => (
                <tr
                  key={a.id}
                  style={{
                    background: selectedAgentId === a.id
                      ? 'var(--cc-surface-container-high)'
                      : undefined,
                  }}
                >
                  <td>
                    <input
                      type="radio"
                      name="selected_agent"
                      checked={selectedAgentId === a.id}
                      onChange={() => setSelectedAgentId(a.id)}
                    />
                  </td>
                  <td>{a.name}</td>
                  <td>
                    <code>{a.slug}</code>
                  </td>
                  <td>{a.skills_count}</td>
                  <td>
                    <span className={`${styles.badge} ${a.active ? styles.badge_cloned : ''}`}>
                      {a.active ? 'ativo' : 'inativo'}
                    </span>
                  </td>
                  <td className={styles.actions}>
                    <button
                      className={styles.actionBtn}
                      onClick={() => startEditAgent(a)}
                      title="Editar"
                    >
                      <span className={styles.icon}>edit</span>
                    </button>
                    <button
                      className={`${styles.actionBtn} ${styles.actionBtnDanger}`}
                      onClick={() => handleDeleteAgent(a.id)}
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

      {/* ── Skills do agente selecionado ────────────────────────── */}
      {selectedAgent && (
        <section className={styles.section}>
          <h2 className={styles.sectionTitle}>
            Skills do agente: {selectedAgent.name}
          </h2>
          <p className={styles.sectionDesc}>
            Skills são pedaços de documentação que o agente consulta para responder.
            Pode importar de uma URL (Confluence, GitHub, etc.) ou criar manual.{' '}
            <Link to="/skills" className={styles.backLink}>
              Ver todas as skills →
            </Link>
          </p>

          {/* Importar de URL */}
          <form
            onSubmit={handleImportUrl}
            className={styles.form}
            style={{ marginBottom: '1rem' }}
          >
            <div className={styles.formRow}>
              <label className={styles.label} style={{ flex: 3 }}>
                Importar de URL
                <input
                  className={styles.input}
                  value={importUrl}
                  onChange={(e) => setImportUrl(e.target.value)}
                  placeholder="https://share.linx.com.br/pages/viewpage.action?pageId=11573726"
                  type="url"
                />
              </label>
              <button
                type="submit"
                className={styles.submitBtn}
                disabled={!importUrl || importing}
                style={{ alignSelf: 'flex-end' }}
              >
                {importing ? 'Importando…' : 'Importar'}
              </button>
            </div>
            {importError && <p className={styles.errorMsg}>{importError}</p>}
          </form>

          {/* Lista de skills */}
          {skills.length === 0 ? (
            <p className={styles.hint}>Nenhuma skill ainda. Importe uma URL ou crie manual abaixo.</p>
          ) : (
            <table className={styles.table}>
              <thead>
                <tr>
                  <th>Título</th>
                  <th>Slug</th>
                  <th>Embed</th>
                  <th>Status</th>
                  <th>Fonte</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {skills.map((s) => (
                  <tr key={s.id}>
                    <td>{s.title}</td>
                    <td>
                      <code>{s.slug}</code>
                    </td>
                    <td>
                      <span
                        className={styles.badge}
                        title={s.has_embedding ? 'Embedding calculado' : 'Sem embedding (busca lexical apenas)'}
                      >
                        {s.has_embedding ? '✓' : '—'}
                      </span>
                    </td>
                    <td>
                      <button
                        className={styles.actionBtn}
                        onClick={() => handleToggleSkillActive(s)}
                        title={s.active ? 'Desactivar' : 'Activar'}
                      >
                        <span className={styles.icon}>
                          {s.active ? 'visibility' : 'visibility_off'}
                        </span>
                      </button>
                    </td>
                    <td className={styles.urlCell} title={s.source_url ?? ''}>
                      {s.source_url ? (
                        <a href={s.source_url} target="_blank" rel="noreferrer">
                          link
                        </a>
                      ) : (
                        <span style={{ opacity: 0.5 }}>manual</span>
                      )}
                    </td>
                    <td className={styles.actions}>
                      <button
                        className={`${styles.actionBtn} ${styles.actionBtnDanger}`}
                        onClick={() => handleDeleteSkill(s.id)}
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

          {/* Form criar manual */}
          <details style={{ marginTop: '1rem' }}>
            <summary
              style={{ cursor: 'pointer', color: 'var(--cc-on-surface-variant)', fontSize: '0.85rem' }}
            >
              + Criar skill manualmente
            </summary>
            <form onSubmit={handleSaveSkill} className={styles.form} style={{ marginTop: '0.5rem' }}>
              <label className={styles.label}>
                Título
                <input
                  className={styles.input}
                  value={skillForm.title}
                  onChange={(e) => setSkillForm((p) => ({ ...p, title: e.target.value }))}
                  placeholder="Ex.: NFS-e — Configuração no Gerencial"
                  required
                />
              </label>
              <label className={styles.label}>
                Resumo (curto, mostrado no contexto do LLM)
                <input
                  className={styles.input}
                  value={skillForm.summary ?? ''}
                  onChange={(e) => setSkillForm((p) => ({ ...p, summary: e.target.value }))}
                  placeholder="Como configurar emissão de NFS-e no AutoSystem"
                />
              </label>
              <label className={styles.label}>
                Conteúdo (markdown)
                <textarea
                  className={styles.input}
                  value={skillForm.content}
                  onChange={(e) => setSkillForm((p) => ({ ...p, content: e.target.value }))}
                  rows={10}
                  style={{ fontFamily: 'monospace', resize: 'vertical' }}
                  required
                />
              </label>
              {skillFormError && <p className={styles.errorMsg}>{skillFormError}</p>}
              <button className={styles.submitBtn} type="submit" disabled={savingSkill}>
                {savingSkill ? 'Salvando…' : 'Criar skill'}
              </button>
            </form>
          </details>
        </section>
      )}
    </div>
  )
}
