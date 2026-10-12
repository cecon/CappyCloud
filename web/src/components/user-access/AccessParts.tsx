import type { ReactNode } from 'react'
import { LoaderCircle } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import type { AiModel } from '../../api'

type AccessListProps<T extends { id: string }> = {
  available: T[] | null; allowed: Set<string>; busy: Set<string>
  renderLabel: (item: T) => ReactNode; onToggle: (id: string) => void
}

export function AccessList<T extends { id: string }>({ available, allowed, busy, renderLabel, onToggle }: AccessListProps<T>) {
  if (available === null) {
    return (
      <div className="flex justify-center py-12">
        <Spinner />
      </div>
    )
  }
  if (available.length === 0) {
    return <p className="py-12 text-center text-sm text-muted-foreground">Nenhum recurso cadastrado.</p>
  }
  return (
    <div className="space-y-2">
      {available.map((item) => (
        <AccessRow
          key={item.id}
          busy={busy.has(item.id)}
          checked={allowed.has(item.id)}
          label={renderLabel(item)}
          resourceId={item.id}
          onToggle={onToggle}
        />
      ))}
    </div>
  )
}

export function AccessRow({
  busy, checked, label, resourceId, onToggle,
}: {
  busy: boolean; checked: boolean; label: ReactNode; resourceId: string; onToggle: (id: string) => void
}) {
  const inputId = `access-${resourceId}`
  return (
    <div
      className={cn(
        'flex min-h-11 items-center justify-between gap-3 rounded-md border border-border bg-card px-3 py-2 text-sm transition-colors hover:bg-accent/50',
        busy && 'cursor-wait opacity-75',
      )}
    >
      <div className="flex min-w-0 flex-1 items-center gap-3">
        <input id={inputId} type="checkbox" className="size-4 shrink-0 accent-primary" checked={checked} disabled={busy} onChange={() => onToggle(resourceId)} />
        <label
          htmlFor={inputId}
          className={cn('min-w-0 flex-1', busy ? 'cursor-wait' : 'cursor-pointer')}
        >
          {label}
        </label>
      </div>
      {busy && <Spinner className="size-4 shrink-0" />}
    </div>
  )
}

export function ResourceLabel({ title, badge }: { title: string; badge: string }) {
  return (
    <div className="flex min-w-0 flex-wrap items-center gap-2">
      <span className="truncate font-medium">{title}</span>
      <Badge variant="outline" className="max-w-full truncate text-muted-foreground">{badge}</Badge>
    </div>
  )
}

export function ModelLabel({ model }: { model: AiModel }) {
  const variant = model.tier === 'free' ? 'success' : model.tier === 'paid' ? 'secondary' : 'outline'
  return (
    <div className="flex min-w-0 flex-wrap items-center gap-2">
      <span className="truncate font-medium">{model.display_name}</span>
      <Badge variant={variant}>{model.tier}</Badge>
    </div>
  )
}

export function BulkButton({ active, children, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement> & { active: boolean }) {
  return (
    <Button size="sm" variant="secondary" {...props}>
      {active && <Spinner />}
      {children}
    </Button>
  )
}

export function Spinner({ className }: { className?: string }) {
  return <LoaderCircle className={cn('size-4 animate-spin', className)} aria-hidden="true" />
}

export function AccessAlert({ message, onClose }: { message: string; onClose: () => void }) {
  return (
    <div className="rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm" role="alert">
      <div className="flex gap-3">
        <div className="min-w-0 flex-1"><p className="font-semibold text-foreground">Falha</p><p className="mt-1 text-muted-foreground">{message}</p></div>
        <Button type="button" variant="ghost" size="sm" onClick={onClose}>
          Fechar
        </Button>
      </div>
    </div>
  )
}
