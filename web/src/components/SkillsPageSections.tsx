import type { Skill, SkillCreate, Workspace } from '../api'
import { Modal } from './ui/legacy'
import styles from '../pages/settings.module.css'

type FilterMode = 'all' | 'active'

type SkillsPageSectionsProps = {
  filterMode: FilterMode
  onFilterChange: (mode: FilterMode) => void
  loading: boolean
  error: string | null
  workspaces: Workspace[]
  filteredSkills: Skill[]
  formOpen: boolean
  editingSkillId: string | null
  onCreate: () => void
  onEdit: (s: Skill) => void
  onCancelForm: () => void
  onToggleActive: (s: Skill) => void
  onDelete: (id: string) => void
  skillForm: SkillCreate
  setSkillForm: React.Dispatch<React.SetStateAction<SkillCreate>>
  skillFormError: string | null
  savingSkill: boolean
  onSaveSkill: (e: React.FormEvent) => void
}

export function SkillsPageSections(p: SkillsPageSectionsProps) {
  const repoNameById = new Map(p.workspaces.map((workspace) => [workspace.id, workspace.name]))
  const editing = p.editingSkillId !== null

  return (
    <div className={styles.crudLayout}>
      <section className={styles.section}>
        <div className={styles.crudHeader}>
          <div>
            <h2 className={styles.sectionTitle}>Skills cadastradas</h2>
            <p className={styles.sectionDesc}>
              {p.filteredSkills.length} item(ns) para uso dinamico no contexto do agente.
            </p>
          </div>
          <div className={styles.crudToolbar}>
            <select
              className={`${styles.input} ${styles.compactSelect}`}
              value={p.filterMode}
              onChange={(e) => p.onFilterChange(e.target.value as FilterMode)}
              aria-label="Filtrar skills"
            >
              <option value="all">Todas</option>
              <option value="active">Ativas</option>
            </select>
            <button type="button" className={styles.submitBtn} onClick={p.onCreate}>
              <span className={styles.icon}>add</span>
              Nova skill
            </button>
          </div>
        </div>
        {p.loading && <p className={styles.hint}>Carregando...</p>}
        {p.error && <p className={styles.errorMsg}>{p.error}</p>}

        {p.filteredSkills.length === 0 && !p.loading ? (
          <p className={styles.hint}>Nenhuma skill neste filtro.</p>
        ) : (
          <table className={styles.table}>
            <thead>
              <tr>
                <th>Repo</th>
                <th>Titulo</th>
                <th>Descricao</th>
                <th>Status</th>
                <th style={{ textAlign: 'right' }}>Acoes</th>
              </tr>
            </thead>
            <tbody>
              {p.filteredSkills.map((s) => (
                <tr key={s.id} className={p.editingSkillId === s.id ? styles.selectedRow : undefined}>
                  <td>{s.repository_id ? (repoNameById.get(s.repository_id) ?? 'Repo removido') : 'Global'}</td>
                  <td>{s.title}</td>
                  <td>
                    <span className={styles.descriptionCell} title={s.summary || s.content}>
                      {s.summary || s.content}
                    </span>
                  </td>
                  <td>
                    <button
                      className={`${styles.statusPill} ${s.active ? styles.statusPillOn : styles.statusPillOff}`}
                      onClick={() => p.onToggleActive(s)}
                      title={s.active ? 'Desativar' : 'Ativar'}
                    >
                      {s.active ? 'Ativa' : 'Inativa'}
                    </button>
                  </td>
                  <td className={styles.actions}>
                    <button
                      className={styles.actionBtn}
                      onClick={() => p.onEdit(s)}
                      title="Editar"
                      aria-label={`Editar ${s.title}`}
                    >
                      <span className={styles.icon}>edit</span>
                    </button>
                    <button
                      className={`${styles.actionBtn} ${styles.actionBtnDanger}`}
                      onClick={() => p.onDelete(s.id)}
                      title="Remover"
                      aria-label={`Remover ${s.title}`}
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

      <Modal
        opened={p.formOpen}
        onClose={p.onCancelForm}
        title={editing ? 'Editar skill' : 'Nova skill'}
        size="38rem"
      >
        <p className={styles.sectionDesc}>
          Defina o repo, titulo e a regra curta que o agente deve receber.
        </p>
        <form onSubmit={p.onSaveSkill} className={styles.form}>
          <label className={styles.label}>
            Repositorio
            <select
              className={styles.input}
              value={p.skillForm.repository_id}
              onChange={(e) => p.setSkillForm((prev) => ({ ...prev, repository_id: e.target.value }))}
              required
            >
              {!p.skillForm.repository_id && (
                <option value="" disabled>Selecione um repositorio...</option>
              )}
              {p.workspaces.map((workspace) => (
                <option key={workspace.id} value={workspace.id}>{workspace.name}</option>
              ))}
            </select>
          </label>
          <label className={styles.label}>
            Titulo
            <input
              className={styles.input}
              value={p.skillForm.title}
              onChange={(e) => p.setSkillForm((prev) => ({ ...prev, title: e.target.value }))}
              placeholder="Ex.: NFS-e - Configuracao"
              required
            />
          </label>
          <label className={styles.label}>
            Descricao
            <textarea
              className={styles.input}
              value={p.skillForm.summary ?? ''}
              onChange={(e) => p.setSkillForm((prev) => ({ ...prev, summary: e.target.value }))}
              placeholder="Quando esta skill deve ser usada e qual regra o agente precisa seguir."
              rows={4}
              style={{ resize: 'vertical' }}
              required
            />
          </label>
          {p.skillFormError && <p className={styles.errorMsg}>{p.skillFormError}</p>}
          <div className={styles.formActions}>
            <button type="button" className={styles.secondaryBtn} onClick={p.onCancelForm}>
              Cancelar
            </button>
            <button className={styles.submitBtn} type="submit" disabled={p.savingSkill}>
              {p.savingSkill ? 'Salvando...' : editing ? 'Salvar alteracoes' : 'Criar skill'}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  )
}

export type { FilterMode }
