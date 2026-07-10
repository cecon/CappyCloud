import type React from 'react'
import { Paperclip, Send, Square } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { cn } from '@/lib/utils'

export type ChatComposerProps = {
  value: string
  onChange: (value: string) => void
  onSend: () => void
  onStop?: () => void
  onAttach?: () => void
  disabled?: boolean
  streaming?: boolean
  placeholder?: string
  context?: React.ReactNode
  className?: string
}

export function ChatComposer({
  value,
  onChange,
  onSend,
  onStop,
  onAttach,
  disabled,
  streaming,
  placeholder = 'Mensagem ao agente...',
  context,
  className,
}: ChatComposerProps) {
  const canSend = value.trim().length > 0 && !disabled
  return (
    <div className={cn('border-t border-border bg-background p-3', className)}>
      <div className="mx-auto max-w-4xl rounded-lg border border-input bg-card shadow-sm">
        <div className="flex items-end gap-2 p-2">
          {onAttach && (
            <Button type="button" size="icon" variant="ghost" onClick={onAttach} disabled={disabled} title="Anexar arquivo">
              <Paperclip className="size-4" />
            </Button>
          )}
          <Textarea
            value={value}
            onChange={(event) => onChange(event.currentTarget.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter' && !event.shiftKey && canSend) {
                event.preventDefault()
                onSend()
              }
            }}
            disabled={disabled}
            placeholder={placeholder}
            className="max-h-48 min-h-12 resize-none border-0 bg-transparent shadow-none focus-visible:ring-0"
          />
          {streaming ? (
            <Button type="button" size="icon" variant="destructive" onClick={onStop} title="Parar agente">
              <Square className="size-4" />
            </Button>
          ) : (
            <Button type="button" size="icon" onClick={onSend} disabled={!canSend} title="Enviar">
              <Send className="size-4" />
            </Button>
          )}
        </div>
        {context && <div className="border-t border-border px-3 py-2 text-xs text-muted-foreground">{context}</div>}
      </div>
    </div>
  )
}
