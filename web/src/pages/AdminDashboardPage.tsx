import { useCallback, useEffect, useMemo, useState } from 'react'
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
  type AccessibleWorkspace,
  type AdminDashboard,
  errorToUserMessage,
  fetchAdminFilterWorkspaces,
  fetchAdminDashboard,
  getToken,
} from '../api'
import { AdminConsole } from '../components/admin/AdminConsole'
import { useAdminWorkspaceIds } from '../hooks/useAdminWorkspaceIds'
import { Badge } from '../components/ui/badge'
import { Button } from '../components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card'
import { Skeleton } from '../components/ui/skeleton'
import { cn } from '../lib/utils'
import {
  ConversationRow,
  CostPeriodCard,
  MetricCard,
  MetricSkeleton,
} from './admin-dashboard/DashboardCards'
import {
  formatCompact,
  formatCurrency,
  formatDateTime,
  formatNumber,
} from './admin-dashboard/format'

const ALL_WORKSPACES = ''

export function AdminDashboardPage() {
  const [data, setData] = useState<AdminDashboard | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [workspaceId, setWorkspaceId] = useState(ALL_WORKSPACES)
  const [workspaces, setWorkspaces] = useState<AccessibleWorkspace[]>([])
  const adminWorkspaceIds = useAdminWorkspaceIds()

  const load = useCallback(async () => {
    const token = getToken()
    if (!token) return
    setLoading(true)
    setError(null)
    try {
      setData(await fetchAdminDashboard(token, { workspaceId: workspaceId || undefined }))
    } catch (err) {
      setError(errorToUserMessage(err))
    } finally {
      setLoading(false)
    }
  }, [workspaceId])

  useEffect(() => {
    void load()
  }, [load])

  useEffect(() => {
    const token = getToken()
    if (token) void fetchAdminFilterWorkspaces(token, adminWorkspaceIds).then(setWorkspaces)
  }, [adminWorkspaceIds])

  const generatedAt = useMemo(
    () => (data ? formatDateTime(data.generated_at) : null),
    [data],
  )
  const workspaceName = workspaces.find((ws) => ws.id === workspaceId)?.name

  return (
    <AdminConsole
      title="Dashboard admin"
      description="Visão rápida das conversas, execução dos agentes e capacidade operacional."
      actions={
        <div className="flex flex-wrap items-center gap-2">
          <select
            className="h-9 rounded-md border border-input bg-background px-3 text-sm"
            value={workspaceId}
            onChange={(e) => setWorkspaceId(e.target.value)}
            aria-label="Filtrar custo por workspace"
          >
            <option value={ALL_WORKSPACES}>Todos os workspaces</option>
            {workspaces.map((ws) => (
              <option key={ws.id} value={ws.id}>
                {ws.name}
              </option>
            ))}
          </select>
          <Button variant="outline" size="sm" onClick={() => void load()} disabled={loading}>
            <RefreshCw className={cn('size-4', loading && 'animate-spin')} />
            Atualizar
          </Button>
        </div>
      }
    >
      {error && (
        <div className="flex items-start gap-2 rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
          <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
          <span>{error}</span>
        </div>
      )}

      <section aria-labelledby="cost-periods-title" className="space-y-2">
        <h2 id="cost-periods-title" className="text-sm font-medium text-muted-foreground">
          Custo {workspaceName ? `do workspace ${workspaceName}` : 'de todos os workspaces'}
        </h2>
        <div className="grid gap-3 sm:grid-cols-3">
          {loading && !data
            ? Array.from({ length: 3 }).map((_, idx) => <MetricSkeleton key={idx} />)
            : (data?.cost_periods ?? []).map((period) => (
                <CostPeriodCard key={period.days} period={period} />
              ))}
        </div>
      </section>

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
              hint={workspaceName ? `Total do workspace ${workspaceName}` : 'Total registrado nas mensagens'}
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
