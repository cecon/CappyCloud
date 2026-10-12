import styles from '../model-picker.module.css'
import { fmtCost, fmtCtx, modelStateLabel, type NormalizedRow } from './helpers'

interface ModelRowProps {
  row: NormalizedRow
  /** Posição na lista filtrada (usada no id do item). */
  listIndex: number
  /** Posição considerando o item "padrão" (usada na navegação por teclado). */
  rowIndex: number
  isActive: boolean
  isSelected: boolean
  onHover: () => void
  onSelect: () => void
}

export function ModelRow({
  row,
  listIndex,
  rowIndex,
  isActive,
  isSelected,
  onHover,
  onSelect,
}: ModelRowProps) {
  return (
    <button
      id={`model-row-${listIndex}`}
      type="button"
      className={`${styles.row} ${isActive ? styles.rowActive : ''} ${
        isSelected ? styles.rowSelected : ''
      }`}
      role="option"
      aria-selected={isSelected}
      data-row-index={rowIndex}
      onMouseEnter={onHover}
      onClick={onSelect}
    >
      <span className={styles.rowProvider} aria-hidden="true">
        {row.provider.slice(0, 2).toUpperCase()}
      </span>
      <span className={styles.rowMain}>
        <span className={styles.rowName}>
          {row.cleanName}
          {modelStateLabel(row.model) && (
            <span className={styles.stateBadge}>
              {modelStateLabel(row.model)}
            </span>
          )}
          {row.model.capabilities?.includes('vision') && (
            <span
              className={styles.visionBadge}
              title="Suporta entrada de imagens (vision-capable)"
              aria-label="Suporta visão"
            >
              <span className={styles.icon}>visibility</span>
              vision
            </span>
          )}
        </span>
        <span className={styles.rowMeta}>
          <span className={styles.rowProviderTag}>
            {row.provider}
          </span>
          <span className={styles.rowModelId}>
            {row.model.model_id}
          </span>
        </span>
      </span>
      <span className={styles.rowStats}>
        <span className={styles.rowPricing}>
          <span className={styles.rowPriceIn}>
            {fmtCost(row.model.input_cost_per_1m_usd)}
          </span>
          <span className={styles.rowPriceSep}>/</span>
          <span className={styles.rowPriceOut}>
            {fmtCost(row.model.output_cost_per_1m_usd)}
          </span>
        </span>
        <span className={styles.rowCtx}>
          {fmtCtx(row.model.context_window)} ctx
        </span>
      </span>
    </button>
  )
}

/** Mensagem da lista vazia: sem modelos autorizados ou sem resultados da busca. */
export function ModelListEmpty({
  allowClear,
  totalRows,
  query,
}: {
  allowClear: boolean
  totalRows: number
  query: string
}) {
  return (
    <>
      {!allowClear && (
        <div className={styles.empty}>
          {totalRows === 0
            ? 'Nenhum modelo autorizado para este usuário.'
            : 'Sem resultados.'}
        </div>
      )}
      {allowClear && totalRows === 0 && (
        <div className={styles.empty}>
          Nenhum modelo autorizado para este usuário.
        </div>
      )}
      {allowClear && totalRows > 0 && (
        <div className={styles.empty}>
          Sem resultados para “{query}”.
        </div>
      )}
    </>
  )
}
