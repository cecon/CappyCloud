import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  SkillsPageSections,
  type FilterMode,
} from '../components/SkillsPageSections'
import {
  AuthError,
  createSkill,
  deleteSkill,
  fetchAgents,
  fetchSkills,
  getToken,
  importSkillFromUrl,
  setToken,
  updateSkill,
  type Agent,
  type Skill,
  type SkillCreate,
} from '../api'
import styles from './settings.module.css'

const EMPTY_SKILL: SkillCreate = {
  agent_id: null,
  title: '',
  summary: '',
  content: '',
  tags: [],
  source_url: null,
}

/**
 * Página dedicada à gestão de skills (knowledge base): lista todas as skills,
 * filtra por agente ou só globais, importa por URL e cria manualmente.
 */
export function SkillsPage() {
  const token = getToken()!

  const [agents, setAgents] = useState<Agent[]>([])
  const [allSkills, setAllSkills] = useState<Skill[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [filterMode, setFilterMode] = useState<FilterMode>('all')

  const [skillForm, setSkillForm] = useState<SkillCreate>(EMPTY_SKILL)
  const [savingSkill, setSavingSkill] = useState(false)
  const [skillFormError, setSkillFormError] = useState<string | null>(null)

  const [importUrl, setImportUrl] = useState('')
  const [importAgentId, setImportAgentId] = useState('')
  const [importing, setImporting] = useState(false)
  const [importError, setImportError] = useState<string | null>(null)

  const agentNameById = useMemo(() => {
    const m = new Map<string, string>()
    for (const a of agents) m.set(a.id, a.name)
    return m
  }, [agents])

  const filteredSkills = useMemo(() => {
    if (filterMode === 'all') return allSkills
    if (filterMode === 'global') return allSkills.filter((s) => !s.agent_id)
    return allSkills.filter((s) => s.agent_id === filterMode)
  }, [allSkills, filterMode])

  useEffect(() => {
    void loadAll()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function loadAll() {
    setLoading(true)
    setError(null)
    try {
      const [agentList, skillList] = await Promise.all([
        fetchAgents(token),
        fetchSkills(token),
      ])
      setAgents(agentList)
      setAllSkills(skillList)
    } catch (err) {
      if (err instanceof AuthError) {
        setToken(null)
        window.location.href = '/login'
        return
      }
      setError(err instanceof Error ? err.message : 'Erro ao carregar skills')
    } finally {
      setLoading(false)
    }
  }

  async function handleSaveSkill(e: React.FormEvent) {
    e.preventDefault()
    setSavingSkill(true)
    setSkillFormError(null)
    try {
      const agent_id = skillForm.agent_id?.trim() ? skillForm.agent_id : null
      const created = await createSkill(token, { ...skillForm, agent_id })
      setAllSkills((prev) => [...prev, created])
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
      setAllSkills((prev) => prev.filter((s) => s.id !== id))
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Erro ao remover skill')
    }
  }

  async function handleToggleSkillActive(s: Skill) {
    try {
      const updated = await updateSkill(token, s.id, { active: !s.active })
      setAllSkills((prev) => prev.map((x) => (x.id === s.id ? updated : x)))
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Erro ao alternar skill')
    }
  }

  async function handleImportUrl(e: React.FormEvent) {
    e.preventDefault()
    if (!importUrl) return
    setImporting(true)
    setImportError(null)
    try {
      const aid = importAgentId.trim() || null
      const created = await importSkillFromUrl(token, importUrl, aid)
      setAllSkills((prev) => [...prev, created])
      setImportUrl('')
    } catch (err) {
      setImportError(err instanceof Error ? err.message : 'Erro desconhecido')
    } finally {
      setImporting(false)
    }
  }

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <Link to="/" className={styles.backLink}>
          <span className={styles.icon}>arrow_back</span>
          Voltar ao chat
        </Link>
        <h1 className={styles.title}>Skills</h1>
        <p className={styles.sectionDesc} style={{ marginTop: '0.35rem' }}>
          Documentação que o agente consulta (RAG). Pode ser global (sem agente) ou
          vinculada a um perfil.{' '}
          <Link to="/agents" className={styles.backLink}>
            Gerir agentes →
          </Link>
        </p>
      </header>

      <SkillsPageSections
        agents={agents}
        filterMode={filterMode}
        onFilterChange={setFilterMode}
        loading={loading}
        error={error}
        importUrl={importUrl}
        setImportUrl={setImportUrl}
        importAgentId={importAgentId}
        setImportAgentId={setImportAgentId}
        importing={importing}
        importError={importError}
        onImportSubmit={handleImportUrl}
        filteredSkills={filteredSkills}
        agentNameById={agentNameById}
        onToggleActive={handleToggleSkillActive}
        onDelete={handleDeleteSkill}
        skillForm={skillForm}
        setSkillForm={setSkillForm}
        skillFormError={skillFormError}
        savingSkill={savingSkill}
        onSaveSkill={handleSaveSkill}
      />
    </div>
  )
}
