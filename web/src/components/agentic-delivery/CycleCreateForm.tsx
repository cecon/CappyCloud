import type { AgenticCycleCreatePayload, Repository } from '../../api'
import styles from './agentic-delivery.module.css'

type Props = {
  repositories: Repository[]
  value: AgenticCycleCreatePayload
  disabled?: boolean
  onChange: (value: AgenticCycleCreatePayload) => void
  onSubmit: () => void
}

function splitLines(value: string): string[] {
  return value
    .split('\n')
    .map((item) => item.trim())
    .filter(Boolean)
}

export function CycleCreateForm({ repositories, value, disabled, onChange, onSubmit }: Props) {
  const selectedRepoId = value.repository_ids[0] ?? ''

  return (
    <section className={styles.panel}>
      <div className={styles.panelHeader}>
        <h2>Ciclo</h2>
        <button
          aria-busy={disabled ? 'true' : 'false'}
          aria-label="Criar ciclo agentic e preparar pacote de trabalho"
          className={styles.primaryButton}
          disabled={disabled}
          onClick={onSubmit}
          title="Criar ciclo e preparar pacote"
          type="button"
        >
          <span className={styles.icon}>playlist_add_check</span>
          Criar e preparar
        </button>
      </div>

      <label className={styles.field}>
        <span>Repositório</span>
        <select
          aria-label="Repositório do ciclo agentic"
          value={selectedRepoId}
          onChange={(event) => onChange({ ...value, repository_ids: [event.currentTarget.value] })}
        >
          <option value="">Selecione</option>
          {repositories.map((repo) => (
            <option key={repo.id} value={repo.id}>
              {repo.name || repo.slug}
            </option>
          ))}
        </select>
      </label>

      <label className={styles.field}>
        <span>Domínio</span>
        <input
          aria-label="Domínio do ciclo agentic"
          value={value.domain_key ?? ''}
          onChange={(event) => onChange({ ...value, domain_key: event.currentTarget.value })}
          placeholder="autosystem"
        />
      </label>

      <label className={styles.field}>
        <span>Título</span>
        <input
          aria-label="Título do ciclo agentic"
          value={value.title}
          onChange={(event) => onChange({ ...value, title: event.currentTarget.value })}
        />
      </label>

      <label className={styles.field}>
        <span>Objetivo de negócio</span>
        <textarea
          aria-label="Objetivo de negócio do ciclo agentic"
          rows={3}
          value={value.business_goal}
          onChange={(event) => onChange({ ...value, business_goal: event.currentTarget.value })}
        />
      </label>

      <label className={styles.field}>
        <span>Limite de escopo</span>
        <textarea
          aria-label="Limite de escopo do ciclo agentic"
          rows={3}
          value={value.scope_boundary}
          onChange={(event) => onChange({ ...value, scope_boundary: event.currentTarget.value })}
        />
      </label>

      <label className={styles.field}>
        <span>Saídas esperadas</span>
        <textarea
          aria-label="Saídas esperadas do ciclo agentic"
          rows={3}
          value={value.expected_outputs.join('\n')}
          onChange={(event) =>
            onChange({ ...value, expected_outputs: splitLines(event.currentTarget.value) })
          }
        />
      </label>

      <label className={styles.field}>
        <span>Critérios de aceitação</span>
        <textarea
          aria-label="Critérios de aceitação do ciclo agentic"
          rows={3}
          value={value.acceptance_expectations.join('\n')}
          onChange={(event) =>
            onChange({ ...value, acceptance_expectations: splitLines(event.currentTarget.value) })
          }
        />
      </label>
    </section>
  )
}
