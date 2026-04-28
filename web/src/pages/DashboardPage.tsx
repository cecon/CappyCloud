import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  AuthError,
  fetchAgents,
  fetchConversations,
  fetchSkills,
  fetchWorkspaces,
  getToken,
  setToken,
  type Agent,
  type Conversation,
  type Skill,
  type Workspace,
} from '../api'
import styles from './dashboard.module.css'

type DashboardData = {
  conversations: Conversation[]
  workspaces: Workspace[]
  agents: Agent[]
  skills: Skill[]
}

const EMPTY_DATA: DashboardData = {
  conversations: [],
  workspaces: [],
  agents: [],
  skills: [],
}

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
        const [conversations, workspaces, agents, skills] = await Promise.all([
          fetchConversations(token),
          fetchWorkspaces(token),
          fetchAgents(token),
          fetchSkills(token),
        ])
        if (!cancelled) {
          setData({ conversations, workspaces, agents, skills })
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

  const activeAgents = useMemo(
    () => data.agents.filter((agent) => agent.active),
    [data.agents],
  )
  const activeSkills = useMemo(
    () => data.skills.filter((skill) => skill.active),
    [data.skills],
  )
  const recentConversations = data.conversations.slice(0, 5)
  const readyWorkspaces = data.workspaces.filter(
    (workspace) => workspace.sandbox_status !== 'error',
  )

  return (
    <main className={styles.page}>
      <section className={styles.hero}>
        <div className={styles.heroContent}>
          <div className={styles.brandRow}>
            <img src="/capybara.png" alt="" className={styles.logo} />
            <span className={styles.eyebrow}>CappyCloud Command Center</span>
          </div>
          <h1 className={styles.title}>Controle suas sessões de agente em um só painel.</h1>
          <p className={styles.subtitle}>
            Abra uma sessão, acompanhe histórico, gerencie agentes e prepare repositórios
            para execução isolada na nuvem.
          </p>
          <div className={styles.heroActions}>
            <Link to="/chat" className={styles.primaryAction}>
              <span className={styles.icon}>bolt</span>
              Nova sessão de agente
            </Link>
            <Link to="/agents" className={styles.secondaryAction}>
              <span className={styles.icon}>support_agent</span>
              Gerenciar agentes
            </Link>
          </div>
        </div>

        <div className={styles.statusDeck} aria-label="Resumo do ambiente">
          <MetricCard value={data.conversations.length} label="sessões" loading={loading} />
          <MetricCard value={readyWorkspaces.length} label="repositórios prontos" loading={loading} />
          <MetricCard value={activeAgents.length} label="agentes ativos" loading={loading} />
          <MetricCard value={activeSkills.length} label="skills ativas" loading={loading} />
        </div>
      </section>

      {error && <p className={styles.error}>{error}</p>}

      <section className={styles.grid}>
        <FeatureCard
          icon="chat_bubble"
          title="Chat de agente"
          description="Execute tarefas em worktrees isolados e acompanhe ferramentas, diff e PR."
          href="/chat"
          cta="Abrir workspace"
        />
        <FeatureCard
          icon="source"
          title="Repositórios"
          description="Configure credenciais, branches padrão e sincronização dos projetos."
          href="/settings"
          cta="Preparar contexto"
        />
        <FeatureCard
          icon="support_agent"
          title="Agentes"
          description="Perfis com system prompt, modelo padrão e comportamento especializado."
          href="/agents"
          cta="Editar agentes"
        />
        <FeatureCard
          icon="history"
          title="Runs"
          description="Tasks em execução, pausadas ou concluídas com timeline de eventos."
          href="/runs"
          cta="Acompanhar execuções"
        />
        <FeatureCard
          icon="analytics"
          title="Analytics"
          description="Métricas operacionais de adoção, saúde e throughput do agente."
          href="/analytics"
          cta="Ver métricas"
        />
      </section>

      <section className={styles.lowerGrid}>
        <div className={styles.panel}>
          <div className={styles.panelHeader}>
            <div>
              <h2 className={styles.panelTitle}>Sessões recentes</h2>
              <p className={styles.panelText}>Retome rapidamente o histórico de trabalho.</p>
            </div>
            <Link to="/chat" className={styles.panelLink}>Ver chat</Link>
          </div>
          {loading ? (
            <p className={styles.muted}>Carregando sessões...</p>
          ) : recentConversations.length > 0 ? (
            <div className={styles.sessionList}>
              {recentConversations.map((conversation) => (
                <Link key={conversation.id} to="/chat" className={styles.sessionItem}>
                  <span className={styles.sessionIcon}>
                    <span className={styles.icon}>history</span>
                  </span>
                  <span className={styles.sessionBody}>
                    <span className={styles.sessionTitle}>{conversation.title}</span>
                    <span className={styles.sessionMeta}>
                      {conversation.repos?.[0]?.slug ?? 'sem repositório'} · {formatDate(conversation.updated_at)}
                    </span>
                  </span>
                  <span className={styles.icon}>chevron_right</span>
                </Link>
              ))}
            </div>
          ) : (
            <p className={styles.muted}>Nenhuma conversa ainda. Comece uma nova sessão.</p>
          )}
        </div>

        <div className={styles.panel}>
          <div className={styles.panelHeader}>
            <div>
              <h2 className={styles.panelTitle}>Próximos controles</h2>
              <p className={styles.panelText}>A fase seguinte pode evoluir esses blocos.</p>
            </div>
          </div>
          <div className={styles.roadmap}>
            <RoadmapItem icon="menu_book" title="Skills" text="Conhecimento global e por agente para orientar RAG." href="/skills" />
            <RoadmapItem icon="analytics" title="Usage dashboard" text="Métricas operacionais disponíveis agora." href="/analytics" />
            <RoadmapItem icon="timeline" title="Timeline" text="Checkpoints e diff entre estados de sessão." />
            <RoadmapItem icon="hub" title="MCP manager" text="Registro e status de ferramentas externas." />
          </div>
        </div>
      </section>
    </main>
  )
}

/** Card numérico usado no resumo do dashboard. */
function MetricCard({ value, label, loading }: { value: number; label: string; loading: boolean }) {
  return (
    <div className={styles.metricCard}>
      <span className={styles.metricValue}>{loading ? '...' : value}</span>
      <span className={styles.metricLabel}>{label}</span>
    </div>
  )
}

/** Atalho principal para uma área do produto. */
function FeatureCard({
  icon,
  title,
  description,
  href,
  cta,
}: {
  icon: string
  title: string
  description: string
  href: string
  cta: string
}) {
  return (
    <Link to={href} className={styles.featureCard}>
      <span className={styles.featureIcon}>
        <span className={styles.icon}>{icon}</span>
      </span>
      <span className={styles.featureTitle}>{title}</span>
      <span className={styles.featureDescription}>{description}</span>
      <span className={styles.featureCta}>
        {cta}
        <span className={styles.icon}>arrow_forward</span>
      </span>
    </Link>
  )
}

/** Item da lista de evolução planejada. */
function RoadmapItem({
  icon,
  title,
  text,
  href,
}: {
  icon: string
  title: string
  text: string
  href?: string
}) {
  const content = (
    <div className={styles.roadmapItem}>
      <span className={styles.roadmapIcon}>
        <span className={styles.icon}>{icon}</span>
      </span>
      <span>
        <strong>{title}</strong>
        <small>{text}</small>
      </span>
    </div>
  )

  if (!href) return content

  return (
    <Link to={href} className={styles.roadmapLink}>
      {content}
    </Link>
  )
}

/** Formata datas curtas sem expor detalhes desnecessários no card. */
function formatDate(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return 'sem data'
  return new Intl.DateTimeFormat('pt-BR', {
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
}
