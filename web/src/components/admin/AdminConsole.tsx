import { AlertTriangle } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { cn } from '@/lib/utils'

type AdminConsoleProps = {
  title: string
  description?: string
  children: React.ReactNode
  actions?: React.ReactNode
  className?: string
}

export function AdminConsole({ title, description, children, actions, className }: AdminConsoleProps) {
  return (
    <div className={cn('space-y-4', className)}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <Badge variant="secondary">Admin</Badge>
            <span className="text-xs text-muted-foreground">Console sobre o chat</span>
          </div>
          <h2 className="mt-2 text-xl font-semibold tracking-normal">{title}</h2>
          {description && <p className="mt-1 max-w-3xl text-sm text-muted-foreground">{description}</p>}
        </div>
        {actions}
      </div>
      {children}
    </div>
  )
}

export function SensitiveActionNotice({ children }: { children?: React.ReactNode }) {
  return (
    <Card className="border-warning/30 bg-warning/5">
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2 text-sm">
          <AlertTriangle className="size-4 text-warning" aria-hidden="true" />
          Acao sensivel
        </CardTitle>
        <CardDescription>
          Confirme impacto, permissao e escopo antes de alterar dados administrativos.
        </CardDescription>
      </CardHeader>
      {children && <CardContent className="pt-0 text-sm text-muted-foreground">{children}</CardContent>}
    </Card>
  )
}
