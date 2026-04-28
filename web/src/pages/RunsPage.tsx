import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  AuthError,
  fetchAgentTaskEvents,
  fetchAgentTasks,
  getToken,
  setToken,
  type AgentTask,
  type AgentTaskEvent,
} from '../api'
import styles from './runs.module.css'

const STATUS_FILTERS = [
  { value: '', label: 'Todas' },
  { value: 'running', label: 'Running' },
  { value: 'paused', label: 'Paused' },
  { value: 'done', label: 'Done' },
  { value: 'error', label: 'Error' },
]

/**
 * Página operacional para acompanhar execuções persistidas do agente.
 */
export function RunsPage() {
  const token = getToken()!
  const [tasks, setTasks] = useState<AgentTask[]>([])
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null)
  const [events, setEvents] = useState<AgentTaskEvent[]>([])
  const [statusFilter, setStatusFilter] = useState('')
  const [loadingTasks, setLoadingTasks] = useState(true)
  const [loadingEvents, setLoadingEvents] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    void loadTasks()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statusFilter])

  useEffect(() => {
    if (!selectedTaskId) {
      setEvents([])
      return
    }
    void loadEvents(selectedTaskId)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedTaskId])

  const selectedTask = useMemo(
    () => tasks.find((task) => task.id === selectedTaskId) ?? tasks[0] ?? null,
    [selectedTaskId, tasks],
  )

  useEffect(() => {
    if (!selectedTaskId && tasks.length > 0) {
      setSelectedTaskId(tasks[0].id)
    }
  }, [selectedTaskId, tasks])

  async function loadTasks() {
    setLoadingTasks(true)
    setError(null)
    try {
      const list = await fetchAgentTasks(token, {
        status: statusFilter || undefined,
        limit: 80,
      })
      setTasks(list)
      if (selectedTaskId && !list.some((task) => task.id === selectedTaskId)) {
        setSelectedTaskId(list[0]?.id ?? null)
      }
    } catch (err) {
      if (err instanceof AuthError) {
        setToken(null)
        window.location.href = '/login'
        return
      }
      setError(err instanceof Error ? err.message : 'Não foi possível carregar execuções.')
    } finally {
      setLoadingTasks(false)
    }
  }

  async function loadEvents(taskId: string) {
    setLoadingEvents(true)
    try {
      const list = await fetchAgentTaskEvents(token, taskId, { limit: 120 })
      setEvents(list)
    } catch (err) {
      if (err instanceof AuthError) {
        setToken(null)
        window.location.href = '/login'
        return
      }
      setError(err instanceof Error ? err.message : 'Não foi possível carregar eventos.')
    } finally {
      setLoadingEvents(false)
    }
  }

  return (
    <main className={styles.page}>
      <header className={styles.header}>
        <div>
          <Link to="/" className={styles.backLink}>
            <span className={styles.icon}>arrow_back</span>
            Dashboard
          </Link>
          <span className={styles.eyebrow}>Agent Operations</span>
          <h1 className={styles.title}>Runs e sessões em execução</h1>
          <p className={styles.subtitle}>
            Acompanhe tasks disparadas por chat, webhooks, routines ou API, com eventos
            persistidos do stream do agente.
          </p>
        </div>
        <button className={styles.refreshBtn} onClick={() => void loadTasks()} disabled={loadingTasks}>
          <span className={styles.icon}>refresh</span>
          Atualizar
        </button>
      </header>

      <section className={styles.summaryGrid}>
        <SummaryCard label="running" value={countByStatus(tasks, 'running')} tone="blue" />
        <SummaryCard label="paused" value={countByStatus(tasks, 'paused')} tone="yellow" />
        <SummaryCard label="done" value={countByStatus(tasks, 'done')} tone="green" />
        <SummaryCard label="error" value={countByStatus(tasks, 'error')} tone="red" />
      </section>

      {error && <p className={styles.error}>{error}</p>}

      <section className={styles.workspace}>
        <aside className={styles.taskPanel}>
          <div className={styles.panelHeader}>
            <div>
              <h2 className={styles.panelTitle}>Execuções</h2>
              <p className={styles.panelText}>{tasks.length} tasks recentes</p>
            </div>
            <select
              className={styles.filterSelect}
              value={statusFilter}
              onChange={(event) => setStatusFilter(event.currentTarget.value)}
              title="Filtrar por status"
            >
              {STATUS_FILTERS.map((filter) => (
                <option key={filter.value || 'all'} value={filter.value}>
                  {filter.label}
                </option>
              ))}
            </select>
          </div>

          <div className={styles.taskList}>
            {loadingTasks ? (
              <p className={styles.muted}>Carregando execuções...</p>
            ) : tasks.length === 0 ? (
              <p className={styles.muted}>Nenhuma execução encontrada.</p>
            ) : (
              tasks.map((task) => (
                <button
                  key={task.id}
                  className={`${styles.taskItem} ${task.id === selectedTask?.id ? styles.taskItemActive : ''}`}
                  onClick={() => setSelectedTaskId(task.id)}
                  type="button"
                >
                  <span className={`${styles.statusDot} ${statusClass(task.status)}`} />
                  <span className={styles.taskBody}>
                    <span className={styles.taskPrompt}>{task.prompt || 'Execução sem prompt'}</span>
                    <span className={styles.taskMeta}>
                      {task.triggered_by} · {task.env_slug || 'sem ambiente'} · {formatDate(task.created_at)}
                    </span>
                  </span>
                </button>
              ))
            )}
          </div>
        </aside>

        <section className={styles.detailPanel}>
          {selectedTask ? (
            <>
              <div className={styles.detailHeader}>
                <div>
                  <span className={`${styles.statusBadge} ${statusClass(selectedTask.status)}`}>
                    {selectedTask.status}
                  </span>
                  <h2 className={styles.detailTitle}>{selectedTask.prompt || 'Execução sem prompt'}</h2>
                  <p className={styles.detailMeta}>
                    {selectedTask.triggered_by} · criada {formatDate(selectedTask.created_at)}
                    {selectedTask.last_event_at ? ` · último evento ${formatDate(selectedTask.last_event_at)}` : ''}
                  </p>
                </div>
                {selectedTask.conversation_id && (
                  <Link to="/chat" className={styles.openChatLink}>
                    <span className={styles.icon}>chat_bubble</span>
                    Abrir chat
                  </Link>
                )}
              </div>

              <div className={styles.eventTimeline}>
                {loadingEvents ? (
                  <p className={styles.muted}>Carregando eventos...</p>
                ) : events.length === 0 ? (
                  <p className={styles.muted}>Esta execução ainda não tem eventos persistidos.</p>
                ) : (
                  events.map((event) => (
                    <EventRow key={event.id} event={event} />
                  ))
                )}
              </div>
            </>
          ) : (
            <div className={styles.emptyDetail}>
              <span className={styles.icon}>history</span>
              <p>Selecione uma execução para ver os eventos.</p>
            </div>
          )}
        </section>
      </section>
    </main>
  )
}

/** Card de contagem por status. */
function SummaryCard({
  label,
  value,
  tone,
}: {
  label: string
  value: number
  tone: 'blue' | 'green' | 'yellow' | 'red'
}) {
  return (
    <div className={`${styles.summaryCard} ${styles[`tone_${tone}`]}`}>
      <span className={styles.summaryValue}>{value}</span>
      <span className={styles.summaryLabel}>{label}</span>
    </div>
  )
}

/** Linha da timeline de eventos de uma task. */
function EventRow({ event }: { event: AgentTaskEvent }) {
  const message = eventMessage(event)
  return (
    <article className={styles.eventRow}>
      <span className={styles.eventMarker}>
        <span className={styles.icon}>{eventIcon(event.event_type)}</span>
      </span>
      <div className={styles.eventContent}>
        <div className={styles.eventTopline}>
          <strong>{event.event_type}</strong>
          <span>{formatDate(event.created_at)}</span>
        </div>
        <p>{message}</p>
      </div>
    </article>
  )
}

/** Conta tasks por status. */
function countByStatus(tasks: AgentTask[], status: string): number {
  return tasks.filter((task) => task.status === status).length
}

/** Escolhe classe visual para status. */
function statusClass(status: string): string {
  if (status === 'running') return styles.statusRunning
  if (status === 'paused') return styles.statusPaused
  if (status === 'done') return styles.statusDone
  if (status === 'error') return styles.statusError
  return styles.statusPending
}

/** Escolhe ícone por tipo de evento. */
function eventIcon(eventType: string): string {
  if (eventType === 'text') return 'notes'
  if (eventType === 'tool_start') return 'play_circle'
  if (eventType === 'tool_result') return 'task_alt'
  if (eventType === 'action_required') return 'pan_tool'
  if (eventType === 'error') return 'error'
  if (eventType === 'status') return 'hourglass_top'
  return 'fiber_manual_record'
}

/** Extrai uma mensagem compacta para visualização de evento. */
function eventMessage(event: AgentTaskEvent): string {
  const data = event.data
  const candidates = [
    data.message,
    data.content,
    data.question,
    data.name,
    data.output,
    data.value,
  ]
  const value = candidates.find((candidate) => typeof candidate === 'string' && candidate.trim())
  if (typeof value === 'string') return truncate(value, 320)
  return truncate(JSON.stringify(data), 320)
}

/** Trunca texto longo para preservar a densidade visual da timeline. */
function truncate(value: string, max: number): string {
  return value.length > max ? `${value.slice(0, max).trim()}...` : value
}

/** Formata datas curtas para cards operacionais. */
function formatDate(value: string | null): string {
  if (!value) return 'sem data'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return 'sem data'
  return new Intl.DateTimeFormat('pt-BR', {
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
}
