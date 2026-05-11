import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  AuthError,
  fetchAgentTasks,
  fetchAiModels,
  fetchConversations,
  getToken,
  setToken,
  type AgentTask,
  type AiModel,
  type Conversation,
} from '../api'
import styles from './analytics.module.css'

type AnalyticsData = {
  tasks: AgentTask[]
  conversations: Conversation[]
  models: AiModel[]
}

const EMPTY_DATA: AnalyticsData = {
  tasks: [],
  conversations: [],
  models: [],
}

/**
 * Dashboard analítico baseado nas métricas operacionais já persistidas.
 */
export function AnalyticsPage() {
  const token = getToken()!
  const [data, setData] = useState<AnalyticsData>(EMPTY_DATA)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    async function loadAnalytics() {
      setLoading(true)
      setError(null)
      try {
        const [tasks, conversations, models] = await Promise.all([
          fetchAgentTasks(token, { limit: 200 }),
          fetchConversations(token),
          fetchAiModels(token),
        ])
        if (!cancelled) setData({ tasks, conversations, models })
      } catch (err) {
        if (err instanceof AuthError) {
          setToken(null)
          window.location.href = '/login'
          return
        }
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Não foi possível carregar analytics.')
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    void loadAnalytics()
    return () => {
      cancelled = true
    }
  }, [token])

  const stats = useMemo(() => buildStats(data.tasks), [data.tasks])
  const activeModels = data.models.filter((model) => model.active)
  const completionRate = data.tasks.length > 0
    ? Math.round((stats.done / data.tasks.length) * 100)
    : 0

  return (
    <main className={styles.page}>
      <header className={styles.header}>
        <div>
          <Link to="/" className={styles.backLink}>
            <span className={styles.icon}>arrow_back</span>
            Dashboard
          </Link>
          <span className={styles.eyebrow}>Operational Analytics</span>
          <h1 className={styles.title}>Métricas do agente</h1>
          <p className={styles.subtitle}>
            Visão de saúde e adoção baseada nas tasks, conversas e modelos já
            persistidos. Custos e tokens entram quando o backend gravar usage do gRPC.
          </p>
        </div>
        <div className={styles.headerNotice}>
          <span className={styles.icon}>info</span>
          Sem custo/tokens persistidos ainda
        </div>
      </header>

      {error && <p className={styles.error}>{error}</p>}

      <section className={styles.metricGrid}>
        <MetricCard label="tasks recentes" value={loading ? '...' : String(data.tasks.length)} />
        <MetricCard label="taxa de conclusão" value={loading ? '...' : `${completionRate}%`} />
        <MetricCard label="duração média" value={loading ? '...' : formatDuration(stats.avgDurationMs)} />
        <MetricCard label="conversas" value={loading ? '...' : String(data.conversations.length)} />
      </section>

      <section className={styles.grid}>
        <div className={styles.panel}>
          <div className={styles.panelHeader}>
            <div>
              <h2 className={styles.panelTitle}>Distribuição por status</h2>
              <p className={styles.panelText}>Últimas {data.tasks.length} execuções carregadas.</p>
            </div>
            <Link to="/runs" className={styles.panelLink}>Ver runs</Link>
          </div>
          <BarList
            items={[
              { label: 'Running', value: stats.running, tone: 'blue' },
              { label: 'Paused', value: stats.paused, tone: 'yellow' },
              { label: 'Done', value: stats.done, tone: 'green' },
              { label: 'Error', value: stats.error, tone: 'red' },
              { label: 'Pending', value: stats.pending, tone: 'muted' },
            ]}
          />
        </div>

        <div className={styles.panel}>
          <div className={styles.panelHeader}>
            <div>
              <h2 className={styles.panelTitle}>Origem das execuções</h2>
              <p className={styles.panelText}>Como as tasks foram disparadas.</p>
            </div>
          </div>
          <BarList items={stats.byTrigger.map(([label, value]) => ({ label, value, tone: 'blue' }))} />
        </div>

        <div className={styles.panel}>
          <div className={styles.panelHeader}>
            <div>
              <h2 className={styles.panelTitle}>Atividade por dia</h2>
              <p className={styles.panelText}>Volume dos últimos dias com runs.</p>
            </div>
          </div>
          <div className={styles.timelineBars}>
            {stats.byDay.length > 0 ? (
              stats.byDay.map(([day, value]) => (
                <div key={day} className={styles.dayBar}>
                  <span>{formatDay(day)}</span>
                  <div className={styles.dayTrack}>
                    <div
                      className={styles.dayFill}
                      style={{ width: `${percentage(value, stats.maxDayCount)}%` }}
                    />
                  </div>
                  <strong>{value}</strong>
                </div>
              ))
            ) : (
              <p className={styles.muted}>Sem atividade suficiente para gráfico.</p>
            )}
          </div>
        </div>

        <div className={styles.panel}>
          <div className={styles.panelHeader}>
            <div>
              <h2 className={styles.panelTitle}>Capacidade configurada</h2>
              <p className={styles.panelText}>Inventário lógico do ambiente atual.</p>
            </div>
          </div>
          <div className={styles.inventory}>
            <InventoryRow icon="smart_toy" label="Modelos ativos" value={activeModels.length} />
            <InventoryRow icon="chat_bubble" label="Conversas salvas" value={data.conversations.length} href="/chat" />
            <InventoryRow icon="history" label="Runs rastreáveis" value={data.tasks.length} href="/runs" />
          </div>
        </div>
      </section>
    </main>
  )
}

/** Card de métrica primária da página. */
function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <div className={styles.metricCard}>
      <span className={styles.metricValue}>{value}</span>
      <span className={styles.metricLabel}>{label}</span>
    </div>
  )
}

/** Lista de barras horizontais simples sem dependência de gráfico. */
function BarList({
  items,
}: {
  items: Array<{ label: string; value: number; tone: 'blue' | 'green' | 'yellow' | 'red' | 'muted' }>
}) {
  const max = Math.max(...items.map((item) => item.value), 1)
  return (
    <div className={styles.barList}>
      {items.map((item) => (
        <div key={item.label} className={styles.barItem}>
          <span className={styles.barLabel}>{item.label}</span>
          <div className={styles.barTrack}>
            <div
              className={`${styles.barFill} ${styles[`tone_${item.tone}`]}`}
              style={{ width: `${percentage(item.value, max)}%` }}
            />
          </div>
          <strong>{item.value}</strong>
        </div>
      ))}
    </div>
  )
}

/** Linha de inventário com link opcional. */
function InventoryRow({
  icon,
  label,
  value,
  href,
}: {
  icon: string
  label: string
  value: number
  href?: string
}) {
  const content = (
    <div className={styles.inventoryRow}>
      <span className={styles.inventoryIcon}>
        <span className={styles.icon}>{icon}</span>
      </span>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  )

  if (!href) return content
  return (
    <Link to={href} className={styles.inventoryLink}>
      {content}
    </Link>
  )
}

/** Agrega métricas derivadas das tasks disponíveis. */
function buildStats(tasks: AgentTask[]) {
  const byTrigger = new Map<string, number>()
  const byDay = new Map<string, number>()
  const durations: number[] = []

  for (const task of tasks) {
    byTrigger.set(task.triggered_by || 'unknown', (byTrigger.get(task.triggered_by || 'unknown') ?? 0) + 1)
    const day = task.created_at.slice(0, 10)
    byDay.set(day, (byDay.get(day) ?? 0) + 1)

    if (task.started_at && task.completed_at) {
      const started = new Date(task.started_at).getTime()
      const completed = new Date(task.completed_at).getTime()
      if (!Number.isNaN(started) && !Number.isNaN(completed) && completed >= started) {
        durations.push(completed - started)
      }
    }
  }

  const byDaySorted = [...byDay.entries()].sort(([a], [b]) => a.localeCompare(b)).slice(-10)

  return {
    running: countStatus(tasks, 'running'),
    paused: countStatus(tasks, 'paused'),
    done: countStatus(tasks, 'done'),
    error: countStatus(tasks, 'error'),
    pending: countStatus(tasks, 'pending'),
    byTrigger: [...byTrigger.entries()].sort((a, b) => b[1] - a[1]).slice(0, 6),
    byDay: byDaySorted,
    maxDayCount: Math.max(...byDaySorted.map(([, value]) => value), 1),
    avgDurationMs: durations.length
      ? durations.reduce((total, value) => total + value, 0) / durations.length
      : 0,
  }
}

function countStatus(tasks: AgentTask[], status: string): number {
  return tasks.filter((task) => task.status === status).length
}

function percentage(value: number, max: number): number {
  if (max <= 0) return 0
  return Math.max(4, Math.round((value / max) * 100))
}

function formatDuration(ms: number): string {
  if (!ms) return 'n/a'
  const seconds = Math.round(ms / 1000)
  if (seconds < 60) return `${seconds}s`
  const minutes = Math.round(seconds / 60)
  if (minutes < 60) return `${minutes}min`
  return `${Math.round(minutes / 60)}h`
}

function formatDay(day: string): string {
  const date = new Date(`${day}T00:00:00`)
  if (Number.isNaN(date.getTime())) return day
  return new Intl.DateTimeFormat('pt-BR', { day: '2-digit', month: 'short' }).format(date)
}
