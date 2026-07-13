import type React from 'react'
import { CheckCircle2, Loader2, Terminal, XCircle } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { cn } from '@/lib/utils'

export type AgentActivityStatus = 'running' | 'done' | 'error'

export type AgentActivityCardProps = {
  title: string
  detail?: string
  status?: AgentActivityStatus
  elapsedLabel?: string
  children?: React.ReactNode
  className?: string
}

export function AgentActivityCard({
  title,
  detail,
  status = 'running',
  elapsedLabel,
  children,
  className,
}: AgentActivityCardProps) {
  const Icon = status === 'running' ? Loader2 : status === 'done' ? CheckCircle2 : XCircle
  return (
    <Card className={cn('border-dashed bg-muted/30', className)}>
      <CardHeader className="flex flex-row items-start gap-3 space-y-0 pb-2">
        <div className="grid size-8 place-items-center rounded-md bg-background text-muted-foreground">
          <Icon className={cn('size-4', status === 'running' && 'animate-spin', status === 'error' && 'text-destructive', status === 'done' && 'text-success')} />
        </div>
        <div className="min-w-0 flex-1">
          <CardTitle className="flex items-center gap-2 text-sm">
            <Terminal className="size-4 text-muted-foreground" />
            {title}
          </CardTitle>
          {detail && <p className="mt-1 text-xs text-muted-foreground">{detail}</p>}
        </div>
        {elapsedLabel && <span className="text-xs text-muted-foreground">{elapsedLabel}</span>}
      </CardHeader>
      {children && <CardContent className="pt-0 text-sm text-muted-foreground">{children}</CardContent>}
    </Card>
  )
}
