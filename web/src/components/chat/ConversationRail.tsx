import { MessageSquare, Plus, Search } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { ScrollArea } from '@/components/ui/scroll-area'
import { cn } from '@/lib/utils'

export type ConversationRailItem = {
  id: string
  title: string
  meta?: string
  active?: boolean
}

type ConversationRailProps = {
  items: ConversationRailItem[]
  countLabel?: string
  search?: string
  onSearchChange?: (value: string) => void
  onNewConversation?: () => void
  onSelectConversation?: (id: string) => void
  className?: string
}

export function ConversationRail({
  items,
  countLabel,
  search = '',
  onSearchChange,
  onNewConversation,
  onSelectConversation,
  className,
}: ConversationRailProps) {
  return (
    <aside className={cn('flex h-full min-h-0 w-72 flex-col border-r border-border bg-card/70', className)}>
      <div className="space-y-3 border-b border-border p-3">
        <div className="flex items-center justify-between gap-2">
          <div>
            <h2 className="text-sm font-semibold">Conversas</h2>
            {countLabel && <p className="text-xs text-muted-foreground">{countLabel}</p>}
          </div>
          <Button size="icon" variant="secondary" onClick={onNewConversation} title="Nova conversa">
            <Plus className="size-4" />
          </Button>
        </div>
        <label className="relative block">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={search}
            onChange={(event) => onSearchChange?.(event.currentTarget.value)}
            placeholder="Buscar conversas"
            className="pl-8"
          />
        </label>
      </div>
      <ScrollArea className="min-h-0 flex-1">
        <div className="space-y-1 p-2">
          {items.length === 0 ? (
            <p className="px-2 py-6 text-center text-sm text-muted-foreground">Nenhuma conversa encontrada.</p>
          ) : (
            items.map((item) => (
              <button
                key={item.id}
                type="button"
                className={cn(
                  'flex w-full items-center gap-2 rounded-md px-2.5 py-2 text-left text-sm transition-colors hover:bg-accent',
                  item.active && 'bg-accent text-accent-foreground',
                )}
                onClick={() => onSelectConversation?.(item.id)}
              >
                <MessageSquare className="size-4 shrink-0 text-muted-foreground" />
                <span className="min-w-0 flex-1">
                  <span className="block truncate font-medium">{item.title}</span>
                  {item.meta && <span className="block truncate text-xs text-muted-foreground">{item.meta}</span>}
                </span>
              </button>
            ))
          )}
        </div>
      </ScrollArea>
    </aside>
  )
}
