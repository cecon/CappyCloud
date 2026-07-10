import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Copy, UserRound } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

export type ChatMessageProps = {
  role: 'user' | 'assistant' | 'system' | string
  content: string
  streaming?: boolean
  meta?: React.ReactNode
  onCopy?: () => void
  className?: string
}

export function ChatMessage({ role, content, streaming, meta, onCopy, className }: ChatMessageProps) {
  const user = role === 'user'
  return (
    <article className={cn('group flex gap-3', user && 'justify-end', className)}>
      {!user && (
        <div className="grid size-8 shrink-0 place-items-center rounded-md bg-primary/15 text-primary">
          C
        </div>
      )}
      <div
        className={cn(
          'max-w-[min(760px,100%)] rounded-lg border px-4 py-3 text-sm shadow-sm',
          user
            ? 'border-primary/30 bg-primary text-primary-foreground'
            : 'border-border bg-card text-card-foreground',
        )}
      >
        <div className="mb-1 flex items-center justify-between gap-3">
          <span className="text-[11px] font-semibold uppercase text-current opacity-70">
            {user ? 'Voce' : 'Agente'}
          </span>
          {onCopy && !user && (
            <Button type="button" variant="ghost" size="icon" className="size-7 opacity-0 group-hover:opacity-100" onClick={onCopy}>
              <Copy className="size-3.5" />
              <span className="sr-only">Copiar resposta</span>
            </Button>
          )}
        </div>
        {user ? (
          <p className="whitespace-pre-wrap leading-6">{content}</p>
        ) : (
          <div className="prose prose-sm max-w-none prose-pre:overflow-x-auto dark:prose-invert">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
            {streaming && <span className="ml-1 inline-block h-4 w-1 animate-pulse bg-primary align-middle" />}
          </div>
        )}
        {meta && <div className="mt-3 border-t border-current/10 pt-2 text-xs opacity-70">{meta}</div>}
      </div>
      {user && (
        <div className="grid size-8 shrink-0 place-items-center rounded-md bg-muted text-muted-foreground">
          <UserRound className="size-4" />
        </div>
      )}
    </article>
  )
}
