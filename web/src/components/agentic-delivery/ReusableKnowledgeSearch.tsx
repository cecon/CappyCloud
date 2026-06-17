import type { AgenticKnowledgeItem } from '../../api'
import styles from './agentic-delivery.module.css'

type Props = {
  query: string
  items: AgenticKnowledgeItem[]
  onQueryChange: (query: string) => void
  onSearch: () => void
}

export function ReusableKnowledgeSearch({ query, items, onQueryChange, onSearch }: Props) {
  return (
    <section className={styles.panel}>
      <div className={styles.panelHeader}>
        <h2>Conhecimento</h2>
        <button className={styles.secondaryButton} type="button" onClick={onSearch}>
          <span className={styles.icon}>search</span>
          Buscar
        </button>
      </div>
      <label className={styles.field}>
        <span>Busca</span>
        <input value={query} onChange={(event) => onQueryChange(event.currentTarget.value)} />
      </label>
      <div className={styles.list}>
        {items.map((item) => (
          <div key={item.id} className={styles.listItem}>
            <span>{item.title}</span>
            {item.needs_review ? <span className={styles.badge}>review</span> : null}
          </div>
        ))}
      </div>
    </section>
  )
}
