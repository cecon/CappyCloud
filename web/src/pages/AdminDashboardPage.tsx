import { useCallback, useEffect, useMemo, useState, type ComponentType } from 'react'
import {
  Activity,
  AlertTriangle,
  Bot,
  Clock3,
  DollarSign,
  GitPullRequest,
  MessageSquareText,
  RefreshCw,
  Server,
  Users,
} from 'lucide-react'
import {
  type AdminDashboard,
  type AdminDashboardConversation,
  errorToUserMessage,
  fetchAdminDashboard,
  getToken,
} from '../api'
import { AdminConsole } from '../components/admin/AdminConsole'
import { Badge } from '../components/ui/badge'
import { Button } from '../components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card'
import { Skeleton } from '../components/ui/skeleton'
import { cn } from '../lib/utils'

type MetricCardProps = {
  label: string
  value: string
  hint: string
  icon: ComponentType<{ className?: string }>
}

const EMPTY_TITLE = 'Nova conversa'

export function AdminDashboardPage() {
  const [data, setData] = useState<AdminDashboard | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    const token = getToken()
    if (!token) return
    setLoading(true)
    setError(null)
    try {
      setData(await fetchAdminDashboard(token))
    } catch (err) {
      setError(errorToUserMessage(err))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const generatedAt = useMemo(
    () => (data ? formatDateTime(data.generated_at) : null),
    [data],
  )

  return (
    <AdminConsole
      title="Dashboard admin"
      description="Visão rápida das conversas, execução dos agentes e capacidade operacional."
      actions={
        <Button variant="outline" size="sm" onClick={() => void load()} disabled={loading}>
          <RefreshCw className={cn('size-4', loading && 'animate-spin')} />
          Atualizar
        </Button>
      }
    >
      {error && (
        <div className="flex items-start gap-2 rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
          <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
          <span>{error}</span>
        </div>
      )}

      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {loading && !data ? (
          Array.from({ length: 8 }).map((_, idx) => <MetricSkeleton key={idx} />)
        ) : data ? (
          <>
            <MetricCard
              icon={MessageSquareText}
              label="Conversas"
              value={formatNumber(data.totals.conversations)}
              hint={`${formatNumber(data.totals.conversations_24h)} nas últimas 24h`}
            />
            <MetricCard
              icon={Bot}
              label="Mensagens"
              value={formatNumber(data.totals.messages)}
              hint={`${formatNumber(data.totals.assistant_messages)} respostas do agente`}
            />
            <MetricCard
              icon={Activity}
              label="Execuções ativas"
              value={formatNumber(data.totals.running_tasks)}
              hint={`${formatNumber(data.totals.failed_tasks_24h)} falhas nas últimas 24h`}
            />
            <MetricCard
              icon={Users}
              label="Usuários"
              value={formatNumber(data.totals.users)}
              hint={`${formatNumber(data.totals.admins)} administradores`}
            />
            <MetricCard
              icon={Server}
              label="Sandboxes"
              value={formatNumber(data.totals.active_sandboxes)}
              hint={`${formatNumber(data.totals.sandboxes)} cadastradas`}
            />
            <MetricCard
              icon={GitPullRequest}
              label="PRs abertos"
              value={formatNumber(data.totals.open_pull_requests)}
              hint="Conversas com PR em aberto ou draft"
            />
            <MetricCard
              icon={Clock3}
              label="Tokens"
              value={formatCompact(data.totals.prompt_tokens + data.totals.completion_tokens)}
              hint={`${formatCompact(data.totals.prompt_tokens)} prompt · ${formatCompact(data.totals.completion_tokens)} output`}
            />
            <MetricCard
              icon={DollarSign}
              label="Custo"
              value={formatCurrency(data.totals.total_cost_usd)}
              hint="Total registrado nas mensagens"
            />
          </>
        ) : null}
      </section>

      <Card>
        <CardHeader className="flex-row items-start justify-between gap-3 space-y-0">
          <div>
            <CardTitle>Últimas conversas</CardTitle>
            <p className="mt-1 text-sm text-muted-foreground">
              {generatedAt ? `Atualizado em ${generatedAt}` : 'Carregando atividade recente'}
            </p>
          </div>
          {data && <Badge variant="secondary">{data.recent_conversations.length} itens</Badge>}
        </CardHeader>
        <CardContent>
          {loading && !data ? (
            <div className="space-y-3">
              {Array.from({ length: 5 }).map((_, idx) => (
                <Skeleton key={idx} className="h-16 w-full" />
              ))}
            </div>
          ) : data && data.recent_conversations.length > 0 ? (
            <div className="divide-y divide-border rounded-md border border-border">
              {data.recent_conversations.map((conversation) => (
                <ConversationRow key={conversation.id} conversation={conversation} />
              ))}
            </div>
          ) : (
            <div className="rounded-md border border-dashed border-border p-8 text-center text-sm text-muted-foreground">
              Nenhuma conversa registrada ainda.
            </div>
          )}
        </CardContent>
      </Card>
    </AdminConsole>
  )
}

function MetricCard({ label, value, hint, icon: Icon }: MetricCardProps) {
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

function MetricSkeleton() {
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

function ConversationRow({ conversation }: { conversation: AdminDashboardConversation }) {
  const title = conversation.title?.trim() || EMPTY_TITLE
  return (
    <article className="grid gap-3 p-4 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-center">
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="truncate text-sm font-semibold">{title}</h3>
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

function formatNumber(value: number): string {
  return new Intl.NumberFormat('pt-BR').format(value)
}

function formatCompact(value: number): string {
  return new Intl.NumberFormat('pt-BR', { notation: 'compact' }).format(value)
}

function formatCurrency(value: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: value >= 1 ? 2 : 4,
  }).format(value)
}

function formatDateTime(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return 'data inválida'
  return new Intl.DateTimeFormat('pt-BR', {
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
}

function formatRelative(value: string): string {
  const time = new Date(value).getTime()
  if (Number.isNaN(time)) return 'sem data'
  const minutes = Math.floor((Date.now() - time) / 60_000)
  if (minutes < 1) return 'agora'
  if (minutes < 60) return `há ${minutes} min`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `há ${hours} h`
  const days = Math.floor(hours / 24)
  return `há ${days} ${days === 1 ? 'dia' : 'dias'}`
}
