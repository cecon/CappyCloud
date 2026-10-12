import type { Conversation, Sandbox, Workspace } from '../../api'
import styles from '../../components/chat.module.css'
import { isSandboxAvailable, sandboxStatusClass, sandboxStatusLabel } from './sandboxStatus'

export function SandboxAccessView({
  sandboxes,
  workspaces,
  conversations,
  onBackToChat,
}: {
  sandboxes: Sandbox[]
  workspaces: Workspace[]
  conversations: Conversation[]
  onBackToChat: () => void
}) {
  const activeSandboxes = sandboxes.filter(isSandboxAvailable)
  const visiblePeople = new Set(
    conversations
      .map((conversation) => conversation.user_email || conversation.user_id)
      .filter((value): value is string => Boolean(value)),
  )
  const visiblePeopleCount = visiblePeople.size || (conversations.length > 0 ? 1 : 0)
  const configuredCount = sandboxes.filter((sandbox) => sandbox.container_status === 'configured').length
  const offlineCount = sandboxes.filter((sandbox) =>
    sandbox.status === 'offline' ||
    sandbox.container_status === 'stopped' ||
    sandbox.container_status === 'not_created',
  ).length

  return (
    <section className={styles.sandboxAccessView}>
      <header className={styles.sandboxAccessHeader}>
        <div>
          <span className={styles.sandboxAccessEyebrow}>Workspace</span>
          <h1>Sandboxes & acessos</h1>
          <p>
            Visão operacional dos ambientes disponíveis, status dos containers e ocupação
            observável pelas sessões carregadas.
          </p>
        </div>
        <button type="button" className={styles.sandboxAccessBackBtn} onClick={onBackToChat}>
          <span className={styles.icon}>chat_bubble</span>
          Voltar ao chat
        </button>
      </header>

      <div className={styles.sandboxMetricsGrid}>
        <SandboxMetricCard label="Sandboxes ativas" value={activeSandboxes.length} detail={`${sandboxes.length} cadastradas`} tone="good" />
        <SandboxMetricCard label="Pessoas visíveis" value={visiblePeopleCount} detail="baseado nas sessões carregadas" tone="neutral" />
        <SandboxMetricCard label="Configuradas" value={configuredCount} detail="prontas para uso" tone="good" />
        <SandboxMetricCard label="Indisponíveis" value={offlineCount} detail="paradas ou não criadas" tone={offlineCount > 0 ? 'warn' : 'neutral'} />
      </div>

      <div className={styles.sandboxAccessContent}>
        <div className={styles.sandboxListPanel}>
          <div className={styles.sandboxPanelHeader}>
            <div>
              <h2>Ambientes</h2>
              <p>{workspaces.length} repositórios visíveis neste workspace</p>
            </div>
          </div>

          {sandboxes.length === 0 ? (
            <div className={styles.sandboxEmptyState}>
              <span className={styles.icon}>dns</span>
              <strong>Nenhuma sandbox disponível</strong>
              <p>Quando uma sandbox for liberada para seu usuário, ela aparecerá aqui.</p>
            </div>
          ) : (
            <div className={styles.sandboxRows}>
              {sandboxes.map((sandbox) => (
                <article className={styles.sandboxRow} key={sandbox.id}>
                  <div className={styles.sandboxRowMain}>
                    <span className={styles.sandboxRowIcon}>
                      <span className={styles.icon}>dns</span>
                    </span>
                    <div>
                      <h3>{sandbox.name}</h3>
                      <p>{sandbox.host}:{sandbox.session_port} · {sandbox.runtime}</p>
                    </div>
                  </div>
                  <div className={styles.sandboxRowMeta}>
                    <span className={`${styles.sandboxStatusBadge} ${sandboxStatusClass(sandbox)}`}>
                      {sandboxStatusLabel(sandbox)}
                    </span>
                    <span className={styles.sandboxUsersBadge}>
                      <span aria-hidden />
                      {visiblePeopleCount} visíveis
                    </span>
                  </div>
                </article>
              ))}
            </div>
          )}
        </div>

        <aside className={styles.sandboxInsightPanel}>
          <h2>Uso por pessoas</h2>
          <p>
            O backend atual lista sandboxes, mas ainda não expõe presença em tempo real por usuário.
            Esta tela já reserva a área para esse número.
          </p>
          <div className={styles.sandboxInsightNumber}>
            <strong>{visiblePeopleCount}</strong>
            <span>pessoas em sessões visíveis</span>
          </div>
          <div className={styles.sandboxInsightNote}>
            Para mostrar “usando agora” com precisão, precisamos persistir heartbeat por sessão ou
            consultar o session_server da sandbox.
          </div>
        </aside>
      </div>
    </section>
  )
}

function SandboxMetricCard({
  label,
  value,
  detail,
  tone,
}: {
  label: string
  value: number
  detail: string
  tone: 'good' | 'warn' | 'neutral'
}) {
  return (
    <div className={`${styles.sandboxMetricCard} ${styles[`sandboxMetricCard_${tone}`]}`}>
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{detail}</small>
    </div>
  )
}
