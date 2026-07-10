import { Link } from 'react-router-dom'
import { X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { cn } from '@/lib/utils'

type AppOverlayProps = {
  title: string
  subtitle?: string
  children: React.ReactNode
  closeTo?: string
  className?: string
}

export function AppOverlay({ title, subtitle, children, closeTo = '/chat', className }: AppOverlayProps) {
  return (
    <section className={cn('flex h-full min-h-0 flex-col rounded-lg border border-border bg-card shadow-sm', className)}>
      <header className="flex min-h-16 items-center justify-between gap-4 border-b border-border px-5">
        <div className="min-w-0">
          <h2 className="truncate text-base font-semibold">{title}</h2>
          {subtitle && <p className="mt-1 truncate text-xs text-muted-foreground">{subtitle}</p>}
        </div>
        <Button variant="ghost" size="icon" asChild title="Fechar painel">
          <Link to={closeTo} aria-label="Fechar painel">
            <X className="size-4" />
          </Link>
        </Button>
      </header>
      <ScrollArea className="min-h-0 flex-1">
        <div className="p-5">{children}</div>
      </ScrollArea>
    </section>
  )
}
