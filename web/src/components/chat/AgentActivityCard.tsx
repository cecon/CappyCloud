import type React from 'react'
import { AlertCircle, CheckCircle2, Clock3, Loader2, Terminal, XCircle } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { cn } from '@/lib/utils'
import type { SubagentActivityEvent } from '@/api'

export type AgentActivityStatus =
  | 'running'
  | 'loading'
  | 'streaming'
  | 'tool-running'
  | 'permission-request'
  | 'permission-timeout'
  | 'warning'
  | 'stalled'
  | 'canceled'
  | 'failed'
  | 'done'
  | 'error'

export type AgentActivityCardProps = {
  title: string
  detail?: string
  status?: AgentActivityStatus
  elapsedLabel?: string
  activities?: SubagentActivityEvent[]
  children?: React.ReactNode
  className?: string
}

function activityStatusLabel(status: AgentActivityStatus) {
  switch (status) {
    case 'done':
      return 'Concluído'
    case 'permission-timeout':
      return 'Permissão expirada'
    case 'warning':
      return 'Atencao'
    case 'stalled':
      return 'Sem novos eventos'
    case 'canceled':
      return 'Cancelado'
    case 'failed':
    case 'error':
      return 'Falhou'
    case 'permission-request':
      return 'Aguardando permissão'
    case 'loading':
      return 'Carregando'
    case 'streaming':
      return 'Respondendo'
    case 'tool-running':
    case 'running':
      return 'Executando'
  }
}

function isActive(status: AgentActivityStatus) {
  return status === 'running' ||
    status === 'loading' ||
    status === 'streaming' ||
    status === 'tool-running' ||
    status === 'permission-request'
}

function isWarning(status: AgentActivityStatus) {
  return status === 'permission-timeout' || status === 'warning' || status === 'stalled' || status === 'canceled'
}

function StatusIcon({ status }: { status: AgentActivityStatus }) {
  if (isActive(status)) return <Loader2 className="size-4 animate-spin" />
  if (status === 'done') return <CheckCircle2 className="size-4 text-success" />
  if (isWarning(status)) return <Clock3 className="size-4 text-amber-500" />
  return <XCircle className="size-4 text-destructive" />
}

export function AgentActivityCard({
  title,
  detail,
  status = 'running',
  elapsedLabel,
  activities,
  children,
  className,
}: AgentActivityCardProps) {
  return (
    <Card className={cn('border-dashed bg-muted/30', className)}>
      <CardHeader className="flex flex-row items-start gap-3 space-y-0 pb-2">
        <div className="grid size-8 place-items-center rounded-md bg-background text-muted-foreground">
          <StatusIcon status={status} />
        </div>
        <div className="min-w-0 flex-1">
          <CardTitle className="flex items-center gap-2 text-sm">
            <Terminal className="size-4 text-muted-foreground" />
            {title}
          </CardTitle>
          {detail && <p className="mt-1 text-xs text-muted-foreground">{detail}</p>}
        </div>
        <span className={cn('shrink-0 rounded-md border px-2 py-0.5 text-xs text-muted-foreground', isWarning(status) && 'border-amber-500/40 text-amber-600', (status === 'failed' || status === 'error') && 'border-destructive/40 text-destructive')}>
          {activityStatusLabel(status)}
        </span>
        {elapsedLabel && <span className="text-xs text-muted-foreground">{elapsedLabel}</span>}
      </CardHeader>
      {(activities?.length || children) && (
        <CardContent className="space-y-2 pt-0 text-sm text-muted-foreground">
          {activities?.length ? (
            <div className="space-y-1.5">
              {activities.map((activity) => (
                <div key={activity.id} className="flex min-w-0 items-start gap-2 rounded-md bg-background/60 px-2 py-1.5">
                  {activity.state === 'failed' ? (
                    <AlertCircle className="mt-0.5 size-3.5 shrink-0 text-destructive" />
                  ) : (
                    <StatusIcon status={activity.state} />
                  )}
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-xs font-medium text-foreground">{activity.name}</div>
                    {activity.detail && <div className="truncate text-xs">{activity.detail}</div>}
                  </div>
                  <span className="shrink-0 text-xs">{activityStatusLabel(activity.state)}</span>
                </div>
              ))}
            </div>
          ) : null}
          {children}
        </CardContent>
      )}
    </Card>
  )
}
