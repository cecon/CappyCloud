import { useRef, useState } from 'react'
import { IconArchive, IconArchiveOff, IconDotsVertical, IconPencil } from '@tabler/icons-react'
import { Menu } from '@/components/ui/legacy'
import { type Conversation, errorToUserMessage } from '../../api'
import styles from '../chat.module.css'

type Props = {
  conversation: Conversation
  active: boolean
  onSelect: () => void
  onRename: (title: string) => Promise<void>
  onArchive: (archived: boolean) => Promise<void>
}

/** Item da barra lateral: abre a conversa; o ⋮ renomeia ou arquiva. */
export function ConversationListItem({ conversation, active, onSelect, onRename, onArchive }: Props) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(conversation.title)
  const [error, setError] = useState<string | null>(null)
  // Esc cancela; o blur que vem em seguida não pode salvar o texto digitado.
  const cancelled = useRef(false)
  const archived = Boolean(conversation.archived_at)

  async function run(action: () => Promise<void>): Promise<boolean> {
    try {
      await action()
      setError(null)
      return true
    } catch (err) {
      setError(errorToUserMessage(err))
      window.setTimeout(() => setError(null), 5000)
      return false
    }
  }

  async function commit() {
    const title = cancelled.current ? '' : draft.trim()
    cancelled.current = false
    setEditing(false)
    if (title && title !== conversation.title) {
      setDraft((await run(() => onRename(title))) ? title : conversation.title)
    } else {
      setDraft(conversation.title)
    }
  }

  return (
    <div className="group relative">
      {editing ? (
        <div className={`${styles.sessionItem} ${styles.sessionItemActive}`}>
          <span className={`${styles.icon} ${styles.sessionIcon}`}>edit</span>
          <input
            autoFocus
            aria-label="Novo nome da conversa"
            className="min-w-0 flex-1 bg-transparent text-inherit outline-none"
            value={draft}
            maxLength={200}
            onChange={(event) => setDraft(event.target.value)}
            onBlur={() => void commit()}
            onKeyDown={(event) => {
              // Quem salva é o blur: Enter só tira o foco (evita salvar duas vezes).
              if (event.key === 'Enter') event.currentTarget.blur()
              if (event.key === 'Escape') {
                cancelled.current = true
                event.currentTarget.blur()
              }
            }}
          />
        </div>
      ) : (
        <button
          type="button"
          className={`${styles.sessionItem} ${active ? styles.sessionItemActive : ''} pr-8`}
          onClick={onSelect}
          onDoubleClick={() => setEditing(true)}
          title={conversation.title}
        >
          <span className={`${styles.icon} ${styles.sessionIcon}`}>{archived ? 'inventory_2' : 'chat_bubble'}</span>
          <span className={styles.sessionLabel}>{conversation.title}</span>
          {!archived && conversation.repos?.[0]?.slug && (
            // O ⋮ ocupa o mesmo canto: a bolinha some quando ele aparece (hover,
            // menu aberto) e no celular, onde o ⋮ fica sempre visível.
            <span
              className={`${styles.sessionEnvDot} max-md:hidden md:group-hover:hidden md:group-has-[[data-state=open]]:hidden`}
              title={conversation.repos[0].slug}
            />
          )}
        </button>
      )}
      {!editing && (
        <Menu>
          <Menu.Target>
            <button
              type="button"
              aria-label={`Ações da conversa ${conversation.title}`}
              className="absolute right-1 top-1/2 flex size-6 -translate-y-1/2 items-center justify-center rounded text-muted-foreground opacity-100 hover:bg-accent md:opacity-0 md:group-hover:opacity-100 md:focus:opacity-100 md:data-[state=open]:opacity-100"
            >
              <IconDotsVertical size={14} />
            </button>
          </Menu.Target>
          <Menu.Dropdown>
            <Menu.Item leftSection={<IconPencil size={14} />} onClick={() => setEditing(true)}>
              Renomear
            </Menu.Item>
            <Menu.Item
              leftSection={archived ? <IconArchiveOff size={14} /> : <IconArchive size={14} />}
              onClick={() => void run(() => onArchive(!archived))}
            >
              {archived ? 'Desarquivar' : 'Arquivar'}
            </Menu.Item>
          </Menu.Dropdown>
        </Menu>
      )}
      {error && <p className="px-3 pb-1 text-xs text-destructive">{error}</p>}
    </div>
  )
}
