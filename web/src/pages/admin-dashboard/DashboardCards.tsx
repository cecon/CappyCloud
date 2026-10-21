import type { ComponentType } from 'react'
import { Link } from 'react-router-dom'
import { DollarSign } from 'lucide-react'
import type { AdminDashboardConversation, AdminDashboardCostPeriod } from '../../api'
import { Badge } from '../../components/ui/badge'
import { Card, CardContent } from '../../components/ui/card'
import { Skeleton } from '../../components/ui/skeleton'
import { formatCompact, formatCurrency, formatNumber, formatRelative } from './format'

type MetricCardProps = {
  label: string
  value: string
  hint: string
  icon: ComponentType<{ className?: string }>
}

const EMPTY_TITLE = 'Nova conversa'

export function MetricCard({ label, value, hint, icon: Icon }: MetricCardProps) {
  return (
    <Card>
      <CardContent className="flex items-start gap-3 p-4">
        <div className="rounded-md border border-border bg-secondary p-2 text-secondary-foreground">
          <Icon className="size-4" aria-hidden="true" />
        </div>
        <div className="min-w-0">
          <p className="text-xs font-medium text-muted-foreground">{label}</p>
          <p className="mt-1 text-2xl font-semibold tracking-normal">{value}</p>
          <p className="mt-1 truncate text-xs text-muted-foreground">{hint}</p>
        </div>
      </CardContent>
    </Card>
  )
}

export function CostPeriodCard({ period }: { period: AdminDashboardCostPeriod }) {
  const tokens = period.prompt_tokens + period.completion_tokens
  return (
    <MetricCard
      icon={DollarSign}
      label={`Últimos ${period.days} dias`}
      value={formatCurrency(period.cost_usd)}
      hint={`${formatNumber(period.conversations)} ${period.conversations === 1 ? 'conversa' : 'conversas'} · ${formatCompact(tokens)} tokens`}
    />
  )
}

export function MetricSkeleton() {
  return (
    <Card>
      <CardContent className="space-y-3 p-4">
        <Skeleton className="h-4 w-24" />
        <Skeleton className="h-8 w-20" />
        <Skeleton className="h-3 w-32" />
      </CardContent>
    </Card>
  )
}

export function ConversationRow({ conversation }: { conversation: AdminDashboardConversation }) {
  const title = conversation.title?.trim() || EMPTY_TITLE
  return (
    <article className="grid gap-3 p-4 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-center">
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <Link to={`/admin/conversations?open=${conversation.id}`} className="truncate text-sm font-semibold hover:underline">
            {title}
          </Link>
          <StatusBadge value={conversation.ci_status} kind="ci" />
          <StatusBadge value={conversation.pr_status} kind="pr" />
        </div>
        <p className="mt-1 text-xs text-muted-foreground">
          {conversation.user_email ?? 'Usuário sem email'} · atualizada {formatRelative(conversation.updated_at)}
        </p>
        {conversation.last_message_preview && (
          <p className="mt-2 line-clamp-2 text-sm text-muted-foreground">
            {conversation.last_message_preview}
          </p>
        )}
      </div>
      <div className="grid grid-cols-2 gap-2 text-xs text-muted-foreground sm:grid-cols-4 lg:min-w-[420px]">
        <InfoPill label="Msgs" value={formatNumber(conversation.message_count)} />
        <InfoPill label="Modelo" value={conversation.model_used ?? 'n/d'} />
        <InfoPill label="Custo" value={formatCurrency(conversation.cost_usd)} />
        <InfoPill label="Última msg" value={conversation.last_message_at ? formatRelative(conversation.last_message_at) : 'n/d'} />
      </div>
    </article>
  )
}

function InfoPill({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0 rounded-md bg-secondary px-3 py-2">
      <span className="block text-[11px] font-medium text-muted-foreground">{label}</span>
      <span className="block truncate text-xs font-semibold text-foreground">{value}</span>
    </div>
  )
}

function StatusBadge({ value, kind }: { value: string; kind: 'ci' | 'pr' }) {
  const normalized = value?.toLowerCase() || 'unknown'
  const variant =
    normalized === 'success' || normalized === 'merged' || normalized === 'open'
      ? 'success'
      : normalized === 'error' || normalized === 'failed'
        ? 'destructive'
        : normalized === 'running' || normalized === 'draft'
          ? 'warning'
          : 'outline'
  return (
    <Badge variant={variant} className="uppercase">
      {kind}: {normalized}
    </Badge>
  )
}
