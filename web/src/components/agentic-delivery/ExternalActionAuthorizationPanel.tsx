import styles from './agentic-delivery.module.css'

type Props = {
  rationale: string
  onRationaleChange: (value: string) => void
  onAuthorize: () => void
}

export function ExternalActionAuthorizationPanel({ rationale, onRationaleChange, onAuthorize }: Props) {
  return (
    <section className={styles.panel}>
      <div className={styles.panelHeader}>
        <h2>Ação externa</h2>
        <button className={styles.dangerButton} type="button" onClick={onAuthorize}>
          <span className={styles.icon}>verified</span>
          Autorizar PR
        </button>
      </div>
      <label className={styles.field}>
        <span>Justificativa</span>
        <textarea rows={3} value={rationale} onChange={(event) => onRationaleChange(event.currentTarget.value)} />
      </label>
    </section>
  )
}
