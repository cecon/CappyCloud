import { useCallback, useEffect, useState } from 'react'
import { type Conversation, fetchConversations, getToken } from '../../api'
import styles from '../chat.module.css'
import { ConversationListItem } from './ConversationListItem'

type Props = {
  activeId: string | null
  /** Muda quando uma conversa é arquivada/desarquivada na lista principal. */
  refreshKey: number
  onSelect: (conversation: Conversation) => void
  onRename: (conversation: Conversation, title: string) => Promise<void>
  onUnarchive: (conversation: Conversation) => Promise<void>
}

/** Rodapé da barra lateral: "Arquivadas (N)", que abre a lista para abrir ou desarquivar. */
export function ArchivedConversations({ activeId, refreshKey, onSelect, onRename, onUnarchive }: Props) {
  const [open, setOpen] = useState(false)
  const [items, setItems] = useState<Conversation[]>([])

  const load = useCallback(async () => {
    const token = getToken()
    if (!token) return
    try {
      setItems(await fetchConversations(token, { archived: true }))
    } catch {
      setItems([])
    }
  }, [])

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0)
    return () => window.clearTimeout(timer)
  }, [load, refreshKey])

  if (items.length === 0) return null

  return (
    <section>
      <button
        type="button"
        className={`${styles.groupLabel} flex w-full items-center justify-between`}
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
      >
        <span>Arquivadas ({items.length})</span>
        <span className={styles.icon}>{open ? 'expand_less' : 'expand_more'}</span>
      </button>
      {open && (
        <div className={styles.groupItems}>
          {items.map((conversation) => (
            <ConversationListItem
              key={conversation.id}
              conversation={conversation}
              active={conversation.id === activeId}
              onSelect={() => onSelect(conversation)}
              onRename={async (title) => {
                await onRename(conversation, title)
                await load()
              }}
              onArchive={async () => {
                await onUnarchive(conversation)
                await load()
              }}
            />
          ))}
        </div>
      )}
    </section>
  )
}
