import { useEffect, useMemo, useState } from 'react'
import type { SlashCommand } from '@/api'
import styles from './SlashCommandMenu.module.css'

export type SlashCommandMenuProps = {
  commands: SlashCommand[]
  query: string
  onPick: (command: SlashCommand) => void
  onDismiss: () => void
}

export function SlashCommandMenu({
  commands,
  query,
  onPick,
  onDismiss,
}: SlashCommandMenuProps) {
  const [active, setActive] = useState(0)
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    return q
      ? commands.filter((command) =>
          `${command.name} ${command.description}`.toLowerCase().includes(q),
        )
      : commands
  }, [commands, query])

  useEffect(() => {
    const startedAt = performance.now()
    const frame = window.requestAnimationFrame(() => {
      window.dispatchEvent(
        new CustomEvent('cappycloud:slash-open-ms', {
          detail: Math.round(performance.now() - startedAt),
        }),
      )
    })
    return () => window.cancelAnimationFrame(frame)
  }, [])

  useEffect(() => {
    const startedAt = performance.now()
    const frame = window.requestAnimationFrame(() => {
      window.dispatchEvent(
        new CustomEvent('cappycloud:slash-filter-ms', {
          detail: Math.round(performance.now() - startedAt),
        }),
      )
    })
    return () => window.cancelAnimationFrame(frame)
  }, [filtered])

  useEffect(() => {
    queueMicrotask(() => setActive(0))
  }, [query])

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault()
        onDismiss()
      }
      if (event.key === 'ArrowDown') {
        event.preventDefault()
        setActive((current) => Math.min(current + 1, Math.max(filtered.length - 1, 0)))
      }
      if (event.key === 'ArrowUp') {
        event.preventDefault()
        setActive((current) => Math.max(current - 1, 0))
      }
      if (event.key === 'Enter' && filtered[active]) {
        event.preventDefault()
        onPick(filtered[active])
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [active, filtered, onDismiss, onPick])

  return (
    <div className={styles.shell} role="listbox" aria-label="Comandos do chat">
      <div className={styles.header}>
        <span>Comandos</span>
        <span>{filtered.length} disponiveis no catalogo</span>
      </div>
      <div className={styles.list}>
        {filtered.length === 0 ? (
          <div className={styles.empty}>Nenhum comando encontrado.</div>
        ) : (
          filtered.map((command, index) => {
            const unavailable =
              command.execution_mode === 'unavailable' ||
              command.availability.state === 'blocked' ||
              command.availability.state === 'unavailable'
            return (
              <button
                key={command.name}
                type="button"
                role="option"
                aria-selected={index === active}
                aria-disabled={unavailable}
                className={[
                  styles.item,
                  index === active ? styles.itemActive : '',
                  unavailable ? styles.itemUnavailable : '',
                ].join(' ')}
                onMouseEnter={() => setActive(index)}
                onClick={() => onPick(command)}
              >
                <span className={styles.name}>{command.name}</span>
                <span className={styles.body}>
                  <span className={styles.description}>{command.description}</span>
                  <span className={styles.meta}>
                    {command.availability.reason ||
                      command.arguments
                        .filter((argument) => argument.required)
                        .map((argument) => argument.label)
                        .join(', ') ||
                      (command.requires_confirmation ? command.confirmation_reason : 'Pronto para usar')}
                  </span>
                </span>
                <span className={styles.badge}>
                  {unavailable
                    ? 'Indisponivel'
                    : command.requires_confirmation
                      ? 'Confirma'
                      : command.category}
                </span>
              </button>
            )
          })
        )}
      </div>
    </div>
  )
}
