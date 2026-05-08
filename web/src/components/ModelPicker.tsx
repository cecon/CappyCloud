/**
 * Selector custom de modelos OpenRouter.
 *
 * Substitui o ``<select>`` nativo (que com 368 opções é impraticável) por um
 * popover com busca incremental e linhas estruturadas:
 *
 *   ┌─────────────────────────────────────────────────────────────┐
 *   │  fabricante  GPT-4o Mini                $0.15 / $0.60       │
 *   │  openai      openai/gpt-4o-mini         128k ctx            │
 *   └─────────────────────────────────────────────────────────────┘
 *
 * Regras aplicadas (skill ui-ux-pro-max):
 *   §1 Accessibility   role="combobox" + ARIA, ESC fecha, focus visível
 *   §2 Touch           items ≥44px de altura, hit area ampla
 *   §4 Style           tokens semânticos, cor de selecção sem ruído
 *   §6 Typography      números monospace, hierarquia clara name>id
 *   §8 Forms           busca com debounce visual via input incremental
 */

import {
  type CSSProperties,
  type KeyboardEvent,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react'
import type { AiModel } from '../api'
import styles from './model-picker.module.css'

export interface ModelPickerProps {
  models: AiModel[]
  /** ID do modelo seleccionado, "" para "modelo padrão". */
  value: string
  onChange: (modelId: string) => void
  disabled?: boolean
  /** Renderização compacta para a barra de contexto (header da conversa). */
  compact?: boolean
  /** Permite o utilizador limpar a selecção via item especial "padrão". */
  allowClear?: boolean
  /** Texto mostrado quando nada está seleccionado. */
  placeholder?: string
}

interface NormalizedRow {
  model: AiModel
  provider: string
  cleanName: string
  searchKey: string
}

function normalize(models: AiModel[]): NormalizedRow[] {
  return models.map((m) => {
    const slashIdx = m.model_id.indexOf('/')
    const provider = slashIdx > 0 ? m.model_id.slice(0, slashIdx) : 'outro'
    const colonIdx = m.display_name.indexOf(':')
    const cleanName =
      colonIdx > 0 ? m.display_name.slice(colonIdx + 1).trim() : m.display_name
    return {
      model: m,
      provider,
      cleanName,
      searchKey: `${m.display_name} ${m.model_id} ${provider}`.toLowerCase(),
    }
  })
}

function fmtCost(value: number | null | undefined): string {
  if (value == null) return '?'
  if (value === 0) return 'free'
  if (value < 0.01) return `$${value.toFixed(4)}`
  return `$${value.toFixed(2)}`
}

function fmtCtx(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${Math.round(n / 1_000)}k`
  return String(n)
}

export function ModelPicker({
  models,
  value,
  onChange,
  disabled = false,
  compact = false,
  allowClear = true,
  placeholder = 'Modelo padrão',
}: ModelPickerProps) {
  const rows = useMemo(() => normalize(models), [models])

  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [activeIndex, setActiveIndex] = useState(0)
  const [popoverStyle, setPopoverStyle] = useState<CSSProperties>({})

  const wrapperRef = useRef<HTMLDivElement>(null)
  const triggerRef = useRef<HTMLButtonElement>(null)
  const popoverRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const listRef = useRef<HTMLDivElement>(null)

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return rows
    const tokens = q.split(/\s+/).filter(Boolean)
    return rows.filter((r) => tokens.every((t) => r.searchKey.includes(t)))
  }, [rows, query])

  const selected = useMemo(
    () => rows.find((r) => r.model.model_id === value) ?? null,
    [rows, value],
  )

  const reposition = useCallback(() => {
    const trigger = triggerRef.current
    if (!trigger) return
    const rect = trigger.getBoundingClientRect()
    const popoverWidth = Math.min(440, Math.max(rect.width, 320))
    const left = Math.min(
      Math.max(8, rect.left),
      window.innerWidth - popoverWidth - 8,
    )
    const spaceBelow = window.innerHeight - rect.bottom - 8
    const spaceAbove = rect.top - 8
    const popoverMaxHeight = Math.min(420, Math.max(spaceBelow, spaceAbove))
    const placeAbove = spaceBelow < 240 && spaceAbove > spaceBelow
    setPopoverStyle({
      position: 'fixed',
      top: placeAbove ? undefined : rect.bottom + 6,
      bottom: placeAbove ? window.innerHeight - rect.top + 6 : undefined,
      left,
      width: popoverWidth,
      maxHeight: popoverMaxHeight,
    })
  }, [])

  useEffect(() => {
    if (!open) return
    reposition()
    setActiveIndex(0)
    setQuery('')
    const t = window.setTimeout(() => inputRef.current?.focus(), 0)
    return () => window.clearTimeout(t)
  }, [open, reposition])

  useEffect(() => {
    if (!open) return
    function onResize() {
      reposition()
    }
    function onDocClick(e: MouseEvent) {
      const t = e.target as Node
      if (
        wrapperRef.current?.contains(t) ||
        popoverRef.current?.contains(t)
      ) {
        return
      }
      setOpen(false)
    }
    function onKey(e: globalThis.KeyboardEvent) {
      if (e.key === 'Escape') {
        e.stopPropagation()
        setOpen(false)
        triggerRef.current?.focus()
      }
    }
    window.addEventListener('resize', onResize)
    window.addEventListener('scroll', onResize, true)
    document.addEventListener('mousedown', onDocClick)
    document.addEventListener('keydown', onKey)
    return () => {
      window.removeEventListener('resize', onResize)
      window.removeEventListener('scroll', onResize, true)
      document.removeEventListener('mousedown', onDocClick)
      document.removeEventListener('keydown', onKey)
    }
  }, [open, reposition])

  useEffect(() => {
    if (!open) return
    const list = listRef.current
    if (!list) return
    const node = list.querySelector<HTMLElement>(
      `[data-row-index="${activeIndex}"]`,
    )
    node?.scrollIntoView({ block: 'nearest' })
  }, [open, activeIndex])

  function handleInputKey(e: KeyboardEvent<HTMLInputElement>) {
    const total = filtered.length + (allowClear ? 1 : 0)
    if (total === 0) return
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setActiveIndex((i) => (i + 1) % total)
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setActiveIndex((i) => (i - 1 + total) % total)
    } else if (e.key === 'Enter') {
      e.preventDefault()
      if (allowClear && activeIndex === 0) {
        onChange('')
        setOpen(false)
        return
      }
      const idx = allowClear ? activeIndex - 1 : activeIndex
      const row = filtered[idx]
      if (row) {
        onChange(row.model.model_id)
        setOpen(false)
      }
    } else if (e.key === 'Tab') {
      setOpen(false)
    }
  }

  const triggerLabel = selected ? selected.cleanName : placeholder
  const triggerProvider = selected?.provider

  return (
    <div ref={wrapperRef} className={styles.wrapper}>
      <button
        ref={triggerRef}
        type="button"
        className={`${styles.trigger} ${compact ? styles.triggerCompact : ''}`}
        onClick={() => !disabled && setOpen((o) => !o)}
        disabled={disabled}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label={`Modelo IA seleccionado: ${triggerLabel}. Clica para mudar.`}
        title={selected ? selected.model.model_id : placeholder}
      >
        <span className={styles.triggerIcon} aria-hidden="true">
          smart_toy
        </span>
        <span className={styles.triggerText}>
          {triggerProvider && (
            <span className={styles.triggerProvider}>{triggerProvider}</span>
          )}
          <span className={styles.triggerName}>{triggerLabel}</span>
        </span>
        <span className={styles.triggerChevron} aria-hidden="true">
          expand_more
        </span>
      </button>

      {open && (
        <div
          ref={popoverRef}
          className={styles.popover}
          style={popoverStyle}
          role="dialog"
          aria-label="Selecionar modelo IA"
        >
          <div className={styles.searchBar}>
            <span className={styles.searchIcon} aria-hidden="true">
              search
            </span>
            <input
              ref={inputRef}
              className={styles.searchInput}
              placeholder="Procurar modelo, fabricante…"
              value={query}
              onChange={(e) => {
                setQuery(e.target.value)
                setActiveIndex(0)
              }}
              onKeyDown={handleInputKey}
              role="combobox"
              aria-expanded
              aria-controls="model-picker-list"
              aria-autocomplete="list"
            />
            <span className={styles.searchCount}>
              {filtered.length}/{rows.length}
            </span>
          </div>

          <div
            ref={listRef}
            id="model-picker-list"
            className={styles.list}
            role="listbox"
            aria-activedescendant={
              filtered.length
                ? `model-row-${allowClear ? Math.max(0, activeIndex - 1) : activeIndex}`
                : undefined
            }
          >
            {allowClear && (
              <button
                type="button"
                className={`${styles.row} ${styles.rowClear} ${
                  activeIndex === 0 ? styles.rowActive : ''
                }`}
                role="option"
                aria-selected={value === ''}
                data-row-index={0}
                onMouseEnter={() => setActiveIndex(0)}
                onClick={() => {
                  onChange('')
                  setOpen(false)
                }}
              >
                <span className={styles.rowMain}>
                  <span className={styles.rowName}>— modelo padrão —</span>
                  <span className={styles.rowSubtle}>
                    Usa o default da configuração do servidor.
                  </span>
                </span>
              </button>
            )}

            {filtered.length === 0 && !allowClear && (
              <div className={styles.empty}>Sem resultados.</div>
            )}
            {filtered.length === 0 && allowClear && (
              <div className={styles.empty}>
                Sem resultados para “{query}”.
              </div>
            )}

            {filtered.map((row, i) => {
              const idx = allowClear ? i + 1 : i
              const isActive = idx === activeIndex
              const isSelected = row.model.model_id === value
              return (
                <button
                  key={row.model.id}
                  id={`model-row-${i}`}
                  type="button"
                  className={`${styles.row} ${isActive ? styles.rowActive : ''} ${
                    isSelected ? styles.rowSelected : ''
                  }`}
                  role="option"
                  aria-selected={isSelected}
                  data-row-index={idx}
                  onMouseEnter={() => setActiveIndex(idx)}
                  onClick={() => {
                    onChange(row.model.model_id)
                    setOpen(false)
                  }}
                >
                  <span className={styles.rowProvider} aria-hidden="true">
                    {row.provider.slice(0, 2).toUpperCase()}
                  </span>
                  <span className={styles.rowMain}>
                    <span className={styles.rowName}>
                      {row.cleanName}
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
            })}
          </div>

          <div className={styles.footer}>
            <span>↑↓ navegar · Enter selecionar · Esc fechar</span>
            <span className={styles.footerHint}>preços por 1M tokens</span>
          </div>
        </div>
      )}
    </div>
  )
}
