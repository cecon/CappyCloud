import { useEffect, useMemo, useState } from 'react'
import {
  AuthError,
  fetchConversations,
  fetchSkills,
  fetchWorkspaces,
  getToken,
  setToken,
  type Conversation,
  type Skill,
  type Workspace,
} from '../api'
import { DashboardSectionHeader } from '../components/dashboard/DashboardSectionHeader'
import { DashboardShell } from '../components/dashboard/DashboardShell'
import { ExecutionQueueCard } from '../components/dashboard/ExecutionQueueCard'
import { FeatureCard } from '../components/dashboard/FeatureCard'
import { HeroCommandPanel } from '../components/dashboard/HeroCommandPanel'
import { MetricCard, MetricStrip } from '../components/dashboard/MetricStrip'
import { RecentSessions } from '../components/dashboard/RecentSessions'
import { TopBar } from '../components/dashboard/TopBar'
import { WorkspaceControls } from '../components/dashboard/WorkspaceControls'
import { WorkspaceHealth } from '../components/dashboard/WorkspaceHealth'
import type { StatusBadgeVariant } from '../components/dashboard/StatusBadge'
import pageStyles from './dashboard-page.module.css'

type DashboardData = {
  conversations: Conversation[]
  workspaces: Workspace[]
  skills: Skill[]
}

const EMPTY_DATA: DashboardData = {
  conversations: [],
  workspaces: [],
  skills: [],
}

const MS_DAY = 86_400_000
const MS_WEEK = 7 * MS_DAY

/**
 * Painel inicial do CappyCloud com atalhos para as superfícies principais.
 */
export function DashboardPage() {
  const token = getToken()!
  const [data, setData] = useState<DashboardData>(EMPTY_DATA)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    async function loadDashboard() {
      setLoading(true)
      setError(null)
      try {
        const [conversations, workspaces, skills] = await Promise.all([
          fetchConversations(token),
          fetchWorkspaces(token),
          fetchSkills(token),
        ])
        if (!cancelled) {
          setData({ conversations, workspaces, skills })
        }
      } catch (err) {
        if (err instanceof AuthError) {
          setToken(null)
          window.location.href = '/login'
          return
        }
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Não foi possível carregar o painel.')
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    void loadDashboard()
    return () => {
      cancelled = true
    }
  }, [token])

  const activeSkills = useMemo(
    () => data.skills.filter((skill) => skill.active),
    [data.skills],
  )
  const recentConversations = data.conversations.slice(0, 8)
  const readyWorkspaces = data.workspaces.filter(
    (workspace) => workspace.sandbox_status !== 'error',
  )

  const sessionsThisWeek = useMemo(() => {
    const cutoff = Date.now() - MS_WEEK
    return data.conversations.filter((c) => new Date(c.created_at).getTime() >= cutoff).length
  }, [data.conversations])

  const lastActivityIso = useMemo(() => {
    if (data.conversations.length === 0) return null
    return data.conversations.reduce(
      (best, c) => (new Date(c.updated_at) > new Date(best) ? c.updated_at : best),
      data.conversations[0].updated_at,
    )
  }, [data.conversations])

  const lastRunLabel = lastActivityIso ? formatRelativePt(lastActivityIso) : 'Nenhuma ainda'

  const controlItems = useMemo(
    () => [
      {
        icon: 'menu_book',
        title: 'Skills',
        text: 'Conhecimento por repositório e RAG orientado.',
        href: '/skills',
        status: 'available' as StatusBadgeVariant,
      },
      {
        icon: 'analytics',
        title: 'Usage dashboard',
        text: 'Métricas operacionais e adoção.',
        href: '/analytics',
        status: 'available' as StatusBadgeVariant,
      },
      {
        icon: 'timeline',
        title: 'Timeline',
        text: 'Checkpoints e diff entre estados de sessão.',
        status: 'planned' as StatusBadgeVariant,
      },
      {
        icon: 'hub',
        title: 'MCP Manager',
        text: 'Registro e status de ferramentas externas.',
        status: 'development' as StatusBadgeVariant,
      },
    ],
    [],
  )

  return (
    <main>
      <DashboardShell>
        <div className={pageStyles.inner}>
          <TopBar />

          <HeroCommandPanel
            sessionsCount={data.conversations.length}
            readyRepos={readyWorkspaces.length}
            activeSkills={activeSkills.length}
            loading={loading}
          />

          <div className={pageStyles.metricsBlock}>
            <MetricStrip>
              <MetricCard
                icon="forum"
                value={data.conversations.length}
                label="Sessões"
                hint={
                  loading
                    ? '…'
                    : sessionsThisWeek > 0
                      ? `+${sessionsThisWeek} esta semana`
                      : 'Sem novas esta semana'
                }
                loading={loading}
              />
              <MetricCard
                icon="source"
                value={readyWorkspaces.length}
                label="Repositórios prontos"
                hint={
                  loading
                    ? '…'
                    : readyWorkspaces.length === 1
                      ? '1 pronto para execução'
                      : `${readyWorkspaces.length} prontos para execução`
                }
                loading={loading}
              />
              <MetricCard
                icon="auto_awesome"
                value={activeSkills.length}
                label="Skills ativas"
                hint={loading ? '…' : 'Sincronizadas'}
                loading={loading}
              />
            </MetricStrip>
          </div>

          {error ? <p className={pageStyles.error}>{error}</p> : null}

          <div className={pageStyles.mainStack}>
            <div className={pageStyles.pairRow}>
              <div className={pageStyles.pairMain}>
                <section className={pageStyles.quickSection} aria-labelledby="quick-actions-title">
                  <DashboardSectionHeader
                    id="quick-actions-title"
                    title="Ações rápidas"
                    subtitle="Atalhos para chat, contexto e observabilidade."
                  />
                  <div className={pageStyles.featureGrid}>
                    <FeatureCard
                      icon="chat_bubble"
                      title="Chat de agente"
                      description="Worktrees isolados, ferramentas, diff e PR em um fluxo só."
                      href="/chat"
                      cta="Abrir workspace"
                    />
                    <FeatureCard
                      icon="source"
                      title="Repositórios"
                      description="Credenciais, branches e sync dos projetos."
                      href="/admin/repositories"
                      cta="Preparar contexto"
                    />
                    <FeatureCard
                      icon="history"
                      title="Runs"
                      description="Tasks em execução ou concluídas com timeline."
                      href="/runs"
                      cta="Acompanhar runs"
                    />
                    <FeatureCard
                      icon="analytics"
                      title="Analytics"
                      description="Throughput, saúde e adoção do agente."
                      href="/analytics"
                      cta="Ver métricas"
                    />
                    <FeatureCard
                      icon="hub"
                      title="MCP Manager"
                      description="Conectores, ferramentas externas e políticas de runtime."
                      href="/admin/sandboxes"
                      cta="Gerenciar MCP"
                    />
                  </div>
                </section>
              </div>
              <aside className={`${pageStyles.pairAside} ${pageStyles.pairAsideStretch}`}>
                <div className={pageStyles.controlsSection}>
                  <DashboardSectionHeader
                    id="workspace-controls-title"
                    title="Controles do workspace"
                    subtitle="Roadmap operacional e módulos em evolução."
                  />
                  <WorkspaceControls items={controlItems} />
                </div>
              </aside>
            </div>

            <div className={`${pageStyles.pairRow} ${pageStyles.pairRowSessions}`}>
              <div className={pageStyles.pairMain}>
                <div className={pageStyles.sessionsBlock}>
                  <RecentSessions
                    conversations={recentConversations}
                    loading={loading}
                    statusFor={conversationSessionStatus}
                    formatDuration={formatSessionDuration}
                    formatDateTime={formatDateTime}
                  />
                </div>
              </div>
              <aside className={`${pageStyles.pairAside} ${pageStyles.pairAsideStack}`}>
                <WorkspaceHealth
                  lastRunLabel={lastRunLabel}
                  sandboxActive={readyWorkspaces.length > 0}
                  mcpConnected={2}
                />
                <ExecutionQueueCard />
              </aside>
            </div>
          </div>
        </div>
      </DashboardShell>
    </main>
  )
}

function conversationSessionStatus(conversation: Conversation): StatusBadgeVariant {
  const updated = new Date(conversation.updated_at).getTime()
  if (Number.isNaN(updated)) return 'completed'
  const minutes = (Date.now() - updated) / 60_000
  if (minutes < 3) return 'running'
  return 'completed'
}

function formatSessionDuration(conversation: Conversation): string {
  const a = new Date(conversation.created_at).getTime()
  const b = new Date(conversation.updated_at).getTime()
  if (Number.isNaN(a) || Number.isNaN(b)) return '—'
  const ms = Math.max(0, b - a)
  if (ms < 60_000) return `${Math.max(1, Math.round(ms / 1000))}s`
  if (ms < 3_600_000) return `${Math.round(ms / 60_000)} min`
  return `${Math.round(ms / 3_600_000)}h`
}

function formatDateTime(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return 'sem data'
  return new Intl.DateTimeFormat('pt-BR', {
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
}

function formatRelativePt(iso: string): string {
  const t = new Date(iso).getTime()
  if (Number.isNaN(t)) return '—'
  const diff = Date.now() - t
  const min = Math.floor(diff / 60_000)
  if (min < 1) return 'agora'
  if (min < 60) return `há ${min} min`
  const h = Math.floor(min / 60)
  if (h < 24) return `há ${h} h`
  const d = Math.floor(h / 24)
  if (d < 7) return `há ${d} ${d === 1 ? 'dia' : 'dias'}`
  const w = Math.floor(d / 7)
  return `há ${w} ${w === 1 ? 'semana' : 'semanas'}`
}
