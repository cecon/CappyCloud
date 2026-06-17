import type { SensitiveSurfacePayload } from '../../api'
import styles from './agentic-delivery.module.css'

type Props = {
  value: SensitiveSurfacePayload
  onChange: (value: SensitiveSurfacePayload) => void
  onSave: () => void
}

export function SensitiveSurfaceManager({ value, onChange, onSave }: Props) {
  return (
    <section className={styles.panel}>
      <div className={styles.panelHeader}>
        <h2>Superfícies</h2>
        <button className={styles.secondaryButton} type="button" onClick={onSave}>
          <span className={styles.icon}>security</span>
          Salvar
        </button>
      </div>
      <label className={styles.field}>
        <span>Nome</span>
        <input value={value.name} onChange={(event) => onChange({ ...value, name: event.currentTarget.value })} />
      </label>
      <label className={styles.field}>
        <span>Palavras-chave</span>
        <input
          value={(value.match_rules.keywords ?? []).join(', ')}
          onChange={(event) =>
            onChange({
              ...value,
              match_rules: {
                ...value.match_rules,
                keywords: event.currentTarget.value.split(',').map((item) => item.trim()).filter(Boolean),
              },
            })
          }
        />
      </label>
    </section>
  )
}
