import type { Agent, Skill, SkillCreate } from '../api'
import styles from '../pages/settings.module.css'

type FilterMode = 'all' | 'global' | string

type SkillsPageSectionsProps = {
  agents: Agent[]
  filterMode: FilterMode
  onFilterChange: (mode: FilterMode) => void
  loading: boolean
  error: string | null
  importUrl: string
  setImportUrl: (v: string) => void
  importAgentId: string
  setImportAgentId: (v: string) => void
  importing: boolean
  importError: string | null
  onImportSubmit: (e: React.FormEvent) => void
  filteredSkills: Skill[]
  agentNameById: Map<string, string>
  onToggleActive: (s: Skill) => void
  onDelete: (id: string) => void
  skillForm: SkillCreate
  setSkillForm: React.Dispatch<React.SetStateAction<SkillCreate>>
  skillFormError: string | null
  savingSkill: boolean
  onSaveSkill: (e: React.FormEvent) => void
}

/**
 * Blocos de UI da página Skills (filtro, import, tabela, formulário de criação).
 */
export function SkillsPageSections(p: SkillsPageSectionsProps) {
  return (
    <>
      <section className={styles.section}>
        <h2 className={styles.sectionTitle}>Filtro</h2>
        <div className={styles.formRow}>
          <label className={styles.label} style={{ flex: 1 }}>
            Mostrar
            <select
              className={styles.input}
              value={p.filterMode}
              onChange={(e) => p.onFilterChange(e.target.value as FilterMode)}
            >
              <option value="all">Todas as skills</option>
              <option value="global">Só globais (sem agente)</option>
              {p.agents.map((a) => (
                <option key={a.id} value={a.id}>
                  Agente: {a.name}
                </option>
              ))}
            </select>
          </label>
        </div>
        {p.loading && <p className={styles.hint}>Carregando…</p>}
        {p.error && <p className={styles.errorMsg}>{p.error}</p>}
      </section>

      <section className={styles.section}>
        <h2 className={styles.sectionTitle}>Importar de URL</h2>
        <form onSubmit={p.onImportSubmit} className={styles.form}>
          <div className={styles.formRow}>
            <label className={styles.label} style={{ flex: 2 }}>
              URL
              <input
                className={styles.input}
                value={p.importUrl}
                onChange={(e) => p.setImportUrl(e.target.value)}
                placeholder="https://…"
                type="url"
              />
            </label>
            <label className={styles.label} style={{ flex: 1 }}>
              Associar a (opcional)
              <select
                className={styles.input}
                value={p.importAgentId}
                onChange={(e) => p.setImportAgentId(e.target.value)}
              >
                <option value="">Global (nenhum agente)</option>
                {p.agents.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.name}
                  </option>
                ))}
              </select>
            </label>
            <button
              type="submit"
              className={styles.submitBtn}
              disabled={!p.importUrl || p.importing}
              style={{ alignSelf: 'flex-end' }}
            >
              {p.importing ? 'Importando…' : 'Importar'}
            </button>
          </div>
          {p.importError && <p className={styles.errorMsg}>{p.importError}</p>}
        </form>
      </section>

      <section className={styles.section}>
        <h2 className={styles.sectionTitle}>Lista ({p.filteredSkills.length})</h2>
        {p.filteredSkills.length === 0 && !p.loading ? (
          <p className={styles.hint}>Nenhuma skill neste filtro.</p>
        ) : (
          <table className={styles.table}>
            <thead>
              <tr>
                <th>Título</th>
                <th>Agente</th>
                <th>Slug</th>
                <th>Embed</th>
                <th>Status</th>
                <th>Fonte</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {p.filteredSkills.map((s) => (
                <tr key={s.id}>
                  <td>{s.title}</td>
                  <td>
                    {s.agent_id ? p.agentNameById.get(s.agent_id) ?? s.agent_id : '—'}
                  </td>
                  <td>
                    <code>{s.slug}</code>
                  </td>
                  <td>
                    <span
                      className={styles.badge}
                      title={
                        s.has_embedding
                          ? 'Embedding calculado'
                          : 'Sem embedding (busca lexical apenas)'
                      }
                    >
                      {s.has_embedding ? '✓' : '—'}
                    </span>
                  </td>
                  <td>
                    <button
                      className={styles.actionBtn}
                      onClick={() => p.onToggleActive(s)}
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
                      onClick={() => p.onDelete(s.id)}
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
        <h2 className={styles.sectionTitle}>Criar skill manualmente</h2>
        <form onSubmit={p.onSaveSkill} className={styles.form}>
          <label className={styles.label}>
            Vincular a agente (opcional)
            <select
              className={styles.input}
              value={p.skillForm.agent_id ?? ''}
              onChange={(e) =>
                p.setSkillForm((prev) => ({
                  ...prev,
                  agent_id: e.target.value || null,
                }))
              }
            >
              <option value="">Global (nenhum agente)</option>
              {p.agents.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name}
                </option>
              ))}
            </select>
          </label>
          <label className={styles.label}>
            Título
            <input
              className={styles.input}
              value={p.skillForm.title}
              onChange={(e) => p.setSkillForm((prev) => ({ ...prev, title: e.target.value }))}
              placeholder="Ex.: NFS-e — Configuração"
              required
            />
          </label>
          <label className={styles.label}>
            Resumo (curto, mostrado no contexto do LLM)
            <input
              className={styles.input}
              value={p.skillForm.summary ?? ''}
              onChange={(e) => p.setSkillForm((prev) => ({ ...prev, summary: e.target.value }))}
              placeholder="Descrição em uma linha"
            />
          </label>
          <label className={styles.label}>
            Conteúdo (markdown)
            <textarea
              className={styles.input}
              value={p.skillForm.content}
              onChange={(e) => p.setSkillForm((prev) => ({ ...prev, content: e.target.value }))}
              rows={10}
              style={{ fontFamily: 'monospace', resize: 'vertical' }}
              required
            />
          </label>
          {p.skillFormError && <p className={styles.errorMsg}>{p.skillFormError}</p>}
          <button className={styles.submitBtn} type="submit" disabled={p.savingSkill}>
            {p.savingSkill ? 'Salvando…' : 'Criar skill'}
          </button>
        </form>
      </section>
    </>
  )
}

export type { FilterMode }
