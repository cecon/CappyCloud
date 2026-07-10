import { AlertCircle, Loader2, ShieldAlert } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { cn } from '@/lib/utils'

type AppStateProps = {
  title: string
  description?: string
  actionLabel?: string
  onAction?: () => void
  className?: string
}

export function LoadingState({ title = 'Carregando', description, className }: Partial<AppStateProps>) {
  return (
    <div className={cn('grid min-h-56 place-items-center p-6', className)}>
      <div className="flex flex-col items-center gap-3 text-center">
        <Loader2 className="size-6 animate-spin text-primary" aria-hidden="true" />
        <div>
          <p className="text-sm font-semibold">{title}</p>
          {description && <p className="mt-1 text-sm text-muted-foreground">{description}</p>}
        </div>
      </div>
    </div>
  )
}

export function EmptyState({ title, description, actionLabel, onAction, className }: AppStateProps) {
  return (
    <Card className={cn('border-dashed', className)}>
      <CardContent className="flex min-h-44 flex-col items-center justify-center gap-3 p-6 text-center">
        <div className="grid size-10 place-items-center rounded-md bg-muted text-muted-foreground">
          <AlertCircle className="size-5" aria-hidden="true" />
        </div>
        <div>
          <p className="text-sm font-semibold">{title}</p>
          {description && <p className="mt-1 max-w-md text-sm text-muted-foreground">{description}</p>}
        </div>
        {actionLabel && onAction && (
          <Button type="button" size="sm" onClick={onAction}>
            {actionLabel}
          </Button>
        )}
      </CardContent>
    </Card>
  )
}

export function ErrorState({ title, description, actionLabel, onAction, className }: AppStateProps) {
  return (
    <Card className={cn('border-destructive/30 bg-destructive/5', className)}>
      <CardContent className="flex min-h-44 flex-col items-center justify-center gap-3 p-6 text-center">
        <div className="grid size-10 place-items-center rounded-md bg-destructive/10 text-destructive">
          <AlertCircle className="size-5" aria-hidden="true" />
        </div>
        <div>
          <p className="text-sm font-semibold">{title}</p>
          {description && <p className="mt-1 max-w-md text-sm text-muted-foreground">{description}</p>}
        </div>
        {actionLabel && onAction && (
          <Button type="button" size="sm" variant="outline" onClick={onAction}>
            {actionLabel}
          </Button>
        )}
      </CardContent>
    </Card>
  )
}

export function ForbiddenState({ title = 'Acesso restrito', description, className }: Partial<AppStateProps>) {
  return (
    <Card className={cn('border-warning/30 bg-warning/5', className)}>
      <CardContent className="flex min-h-44 flex-col items-center justify-center gap-3 p-6 text-center">
        <div className="grid size-10 place-items-center rounded-md bg-warning/10 text-warning">
          <ShieldAlert className="size-5" aria-hidden="true" />
        </div>
        <div>
          <p className="text-sm font-semibold">{title}</p>
          {description && <p className="mt-1 max-w-md text-sm text-muted-foreground">{description}</p>}
        </div>
      </CardContent>
    </Card>
  )
}
