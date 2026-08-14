import type React from 'react'
import { Activity, Bot, Cloud, GitBranch, LockKeyhole, Users } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import type { ContextProgressEvent } from '@/api'

export type ChatContextBarProps = {
  workspace?: string | null
  repository?: string | null
  branch?: string | null
  sandbox?: string | null
  model?: string | null
  permissionMode?: string | null
  collaborators?: number
  contextProgress?: ContextProgressEvent | null
  className?: string
}

function ContextPill({
  icon,
  label,
}: {
  icon: React.ReactNode
  label: React.ReactNode
}) {
  return (
    <span className="inline-flex min-w-0 items-center gap-1.5 rounded-md border border-border bg-muted/40 px-2 py-1 text-xs text-muted-foreground">
      {icon}
      <span className="truncate">{label}</span>
    </span>
  )
}

export function ChatContextBar({
  workspace,
  repository,
  branch,
  sandbox,
  model,
  permissionMode,
  collaborators,
  contextProgress,
  className,
}: ChatContextBarProps) {
  const progressLabel = contextProgress
    ? contextProgress.percent != null
      ? `${contextProgress.label} ${contextProgress.percent}%`
      : contextProgress.limit_value != null && contextProgress.current_value != null
        ? `${contextProgress.label} ${contextProgress.current_value.toLocaleString()}/${contextProgress.limit_value.toLocaleString()}`
        : contextProgress.label
    : null

  return (
    <div className={cn('flex flex-wrap items-center gap-2 border-b border-border bg-background/70 px-3 py-2', className)}>
      <Badge variant="secondary" className="gap-1">
        <Bot className="size-3" />
        Cappy
      </Badge>
      {workspace && <ContextPill icon={<Cloud className="size-3" />} label={workspace} />}
      {repository && <ContextPill icon={<GitBranch className="size-3" />} label={branch ? `${repository}:${branch}` : repository} />}
      {sandbox && <ContextPill icon={<Cloud className="size-3" />} label={sandbox} />}
      {model && <ContextPill icon={<Bot className="size-3" />} label={model} />}
      {permissionMode && <ContextPill icon={<LockKeyhole className="size-3" />} label={permissionMode} />}
      {progressLabel && <ContextPill icon={<Activity className="size-3" />} label={progressLabel} />}
      {collaborators != null && collaborators > 0 && (
        <ContextPill icon={<Users className="size-3" />} label={`${collaborators} online`} />
      )}
    </div>
  )
}
