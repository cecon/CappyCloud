import { useState } from 'react'
import type { PayloadSizeBreakdown } from '../../api'
import styles from '../../components/chat.module.css'
import { formatByteSize } from './formatting'

export function PayloadDiagnosticSummary({ diagnostics }: { diagnostics: PayloadSizeBreakdown }) {
  const [expanded, setExpanded] = useState(false)
  const categories = diagnostics.categories ?? []
  const topCategories = categories.slice(0, 3)
  return (
    <div className={styles.payloadDiagnostic}>
      <button
        type="button"
        className={styles.payloadDiagnosticToggle}
        onClick={() => setExpanded((value) => !value)}
        aria-expanded={expanded}
        aria-label="Alternar detalhes do payload"
      >
        <span className={`${styles.icon} ${styles.payloadDiagnosticIcon}`} aria-hidden="true">
          data_object
        </span>
        <span className={styles.payloadDiagnosticTitle}>Pedido</span>
        <strong className={styles.payloadDiagnosticTotal}>
          {formatByteSize(diagnostics.total_size_bytes)}
        </strong>
        {topCategories.length > 0 && (
          <span className={styles.payloadDiagnosticChips}>
            {topCategories.map((category) => (
              <span className={styles.payloadDiagnosticChip} key={category.key}>
                {category.label} {formatByteSize(category.size_bytes)}
              </span>
            ))}
          </span>
        )}
        {categories.length > 0 && (
          <span className={`${styles.icon} ${styles.payloadDiagnosticChevron}`} aria-hidden="true">
            {expanded ? 'expand_less' : 'expand_more'}
          </span>
        )}
      </button>
      {expanded && categories.length > 0 && (
        <div className={styles.payloadDiagnosticDetails}>
          {categories.map((category) => (
            <div className={styles.payloadDiagnosticRow} key={category.key}>
              <span className={styles.payloadDiagnosticLabel}>{category.label}</span>
              <span className={styles.payloadDiagnosticBar} aria-hidden="true">
                <span
                  className={styles.payloadDiagnosticBarFill}
                  style={{ width: `${Math.min(100, Math.max(0, category.percentage ?? 0))}%` }}
                />
              </span>
              <span className={styles.payloadDiagnosticValue}>
                {formatByteSize(category.size_bytes)}
                {category.percentage != null ? ` · ${category.percentage.toFixed(1)}%` : ''}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
