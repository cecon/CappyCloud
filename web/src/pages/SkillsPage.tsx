import { useEffect, useMemo, useState } from 'react'
import {
  SkillsPageSections,
  type FilterMode,
} from '../components/SkillsPageSections'
import {
  AuthError,
  createSkill,
  deleteSkill,
  fetchSkills,
  fetchWorkspaces,
  getToken,
  setToken,
  updateSkill,
  type Skill,
  type SkillCreate,
  type Workspace,
} from '../api'
import styles from './settings.module.css'

const EMPTY_SKILL: SkillCreate = {
  repository_id: '',
  title: '',
  summary: '',
  content: null,
}

/**
 * Página dedicada à gestão de skills (knowledge base): lista todas as skills,
 * importa por URL e cria conteúdo manualmente.
 */
export function SkillsPage() {
  const token = getToken()!

  const [allSkills, setAllSkills] = useState<Skill[]>([])
  const [workspaces, setWorkspaces] = useState<Workspace[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [filterMode, setFilterMode] = useState<FilterMode>('all')

  const [skillForm, setSkillForm] = useState<SkillCreate>(EMPTY_SKILL)
  const [editingSkillId, setEditingSkillId] = useState<string | null>(null)
  const [formOpen, setFormOpen] = useState(false)
  const [savingSkill, setSavingSkill] = useState(false)
  const [skillFormError, setSkillFormError] = useState<string | null>(null)

  const filteredSkills = useMemo(() => {
    if (filterMode === 'all') return allSkills
    return allSkills.filter((s) => s.active)
  }, [allSkills, filterMode])

  useEffect(() => {
    void loadAll()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function loadAll() {
    setLoading(true)
    setError(null)
    try {
      const [skillList, workspaceList] = await Promise.all([
        fetchSkills(token),
        fetchWorkspaces(token),
      ])
      setAllSkills(skillList)
      setWorkspaces(workspaceList)
      setSkillForm((prev) => ({
        ...prev,
        repository_id: prev.repository_id || workspaceList[0]?.id || '',
      }))
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
      const description = (skillForm.summary || '').trim()
      const payload = {
        repository_id: skillForm.repository_id,
        title: skillForm.title.trim(),
        summary: description,
        content: description,
      }
      if (editingSkillId) {
        const updated = await updateSkill(token, editingSkillId, payload)
        setAllSkills((prev) => prev.map((skill) => (skill.id === editingSkillId ? updated : skill)))
      } else {
        const created = await createSkill(token, payload)
        setAllSkills((prev) => [...prev, created])
      }
      closeForm(skillForm.repository_id)
    } catch (err) {
      setSkillFormError(err instanceof Error ? err.message : 'Erro desconhecido')
    } finally {
      setSavingSkill(false)
    }
  }

  function openCreateForm() {
    setEditingSkillId(null)
    setSkillForm({ ...EMPTY_SKILL, repository_id: workspaces[0]?.id || '' })
    setSkillFormError(null)
    setFormOpen(true)
  }

  function openEditForm(skill: Skill) {
    setEditingSkillId(skill.id)
    setSkillForm({
      repository_id: skill.repository_id || workspaces[0]?.id || '',
      title: skill.title,
      summary: skill.summary || skill.content,
      content: skill.summary || skill.content,
    })
    setSkillFormError(null)
    setFormOpen(true)
  }

  function closeForm(repositoryId = skillForm.repository_id) {
    setEditingSkillId(null)
    setSkillForm({ ...EMPTY_SKILL, repository_id: repositoryId || workspaces[0]?.id || '' })
    setSkillFormError(null)
    setFormOpen(false)
  }

  async function handleDeleteSkill(id: string) {
    if (!confirm('Remover esta skill?? ')) return
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

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <h1 className={styles.title}>Skills</h1>
        <p className={styles.sectionDesc} style={{ marginTop: '0.35rem' }}>
          Regras curtas por repositório que entram no contexto do openclaude.
        </p>
      </header>

      <SkillsPageSections
        filterMode={filterMode}
        onFilterChange={setFilterMode}
        loading={loading}
        error={error}
        workspaces={workspaces}
        filteredSkills={filteredSkills}
        formOpen={formOpen}
        editingSkillId={editingSkillId}
        onCreate={openCreateForm}
        onEdit={openEditForm}
        onCancelForm={() => closeForm()}
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
