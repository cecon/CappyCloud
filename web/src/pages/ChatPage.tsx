import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Burger,
  ScrollArea,
  Stack,
  Text,
} from '@mantine/core'
import { useDisclosure } from '@mantine/hooks'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import {
  AuthError,
  cancelConversation,
  createConversation,
  createConversationPr,
  fetchBranches,
  fetchConversationDiff,
  fetchConversations,
  fetchMessages,
  fetchWorkspaces,
  getToken,
  setToken,
  streamAssistantReply,
  type ActionRequiredEvent,
  type ChatMessage,
  type Conversation,
  type ConversationDiff,
  type Workspace,
} from '../api'
import { ActionRequiredCard } from '../components/ActionRequiredCard'
import { DiffViewer } from '../components/DiffViewer'
import { FileExplorer } from '../components/FileExplorer'
import { ThinkingIndicator } from '../components/ThinkingIndicator'
import { ToolCallCard, type ToolCallState } from '../components/ToolCallCard'
import styles from '../components/chat.module.css'

/** Agrupa conversas em Today / Yesterday / Older */
function groupConversations(convs: Conversation[]): { label: string; items: Conversation[] }[] {
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime()
  const yesterday = today - 86_400_000

  const groups: Record<string, Conversation[]> = { Today: [], Yesterday: [], Older: [] }
  for (const c of convs) {
    const d = new Date(c.created_at ?? c.id).getTime()
    if (d >= today) groups.Today.push(c)
    else if (d >= yesterday) groups.Yesterday.push(c)
    else groups.Older.push(c)
  }
  return Object.entries(groups)
    .filter(([, items]) => items.length > 0)
    .map(([label, items]) => ({ label, items }))
}

/**
 * UI principal: layout IDE estilo "The Silent Architect".
 * Estado vazio → command bar premium centralizada.
 * Estado ativo  → lista de mensagens + input compacto.
 */
export function ChatPage() {
  const token = getToken()!
  const [mobileOpened, { toggle: toggleMobile }] = useDisclosure()

  const [conversations, setConversations] = useState<Conversation[]>([])
  const [activeId, setActiveId] = useState<string | null>(null)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [loading, setLoading] = useState(true)

  const [workspaces, setWorkspaces] = useState<Workspace[]>([])
  const [selectedSlug, setSelectedSlug] = useState<string>('')
  const [selectedBranch, setSelectedBranch] = useState<string>('')

  const [pendingText, setPendingText] = useState('')
  const [pendingTools, setPendingTools] = useState<ToolCallState[]>([])
  const [pendingAction, setPendingAction] = useState<ActionRequiredEvent | null>(null)

  const [sidePanel, setSidePanel] = useState<'none' | 'diff' | 'files'>('none')
  const [diff, setDiff] = useState<ConversationDiff | null>(null)
  const [diffLoading, setDiffLoading] = useState(false)

  const [diffStats, setDiffStats] = useState<{ added: number; removed: number } | null>(null)
  const [prLoading, setPrLoading] = useState(false)
  const [prUrl, setPrUrl] = useState<string | null>(null)
  const [headBranch, setHeadBranch] = useState<string | null>(null)

  const abortControllerRef = useRef<AbortController | null>(null)
  const scrollRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
    }
  }, [messages, pendingText, pendingTools, pendingAction, streaming])

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const [convsResult, wsList] = await Promise.allSettled([
          fetchConversations(token),
          fetchWorkspaces(token),
        ])
        if (cancelled) return

        if (wsList.status === 'fulfilled') {
          setWorkspaces(wsList.value)
        } else if (wsList.reason instanceof AuthError) {
          setToken(null)
          window.location.href = '/login'
          return
        }

        if (convsResult.status === 'fulfilled') {
          setConversations(convsResult.value)
          if (convsResult.value.length > 0) setActiveId((prev) => prev ?? convsResult.value[0].id)
        } else if (convsResult.reason instanceof AuthError) {
          setToken(null)
          window.location.href = '/login'
          return
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => { cancelled = true }
  }, [token])

  useEffect(() => {
    if (!activeId) return
    let cancelled = false
    setDiffStats(null)
    setPrUrl(null)
    setHeadBranch(null)
    ;(async () => {
      const msgs = await fetchMessages(token, activeId)
      if (!cancelled) setMessages(msgs)
    })()
    return () => { cancelled = true }
  }, [activeId, token])

  async function handleStop() {
    abortControllerRef.current?.abort()
    if (activeId) await cancelConversation(token, activeId)
    setStreaming(false)
    setPendingAction(null)
  }

  async function handleCreatePr() {
    if (!activeId) return
    setPrLoading(true)
    try {
      const result = await createConversationPr(token, activeId)
      setPrUrl(result.pr_url)
      setHeadBranch(result.head_branch)
    } catch {
      // silently fail — user can retry
    } finally {
      setPrLoading(false)
    }
  }

  async function handleOpenDiff() {
    if (!activeId) return
    if (sidePanel === 'diff') { setSidePanel('none'); return }
    setSidePanel('diff')
    setDiffLoading(true)
    try {
      const d = await fetchConversationDiff(token, activeId)
      setDiff(d)
    } catch {
      setDiff(null)
    } finally {
      setDiffLoading(false)
    }
  }

  function handleToggleFiles() {
    setSidePanel((p) => p === 'files' ? 'none' : 'files')
  }

  function handleNewChat() {
    setActiveId(null)
    setMessages([])
    setTimeout(() => inputRef.current?.focus(), 50)
  }

  /** Cria conversa e envia a mensagem inicial de uma vez */
  async function handleNewChatWithMessage(text: string) {
    if (!text.trim()) return
    const c = await createConversation(token, null, selectedBranch || null, selectedSlug || null)
    setConversations((prev) => [c, ...prev])
    setActiveId(c.id)
    setMessages([])
    setInput('')

    setStreaming(true)
    setPendingText('')
    setPendingTools([])
    setPendingAction(null)

    const ctrl = new AbortController()
    abortControllerRef.current = ctrl

    const userMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content: text,
      created_at: new Date().toISOString(),
    }
    setMessages([userMsg])

    try {
      await streamAssistantReply(token, c.id, text, {
        onText(accumulated) { setPendingText(accumulated) },
        onToolStart(tool) {
          setPendingTools((prev) => [
            ...prev,
            { id: tool.id, name: tool.name, input: tool.input, done: false },
          ])
        },
        onToolResult(result) {
          setPendingTools((prev) =>
            prev.map((t) =>
              t.id === result.id
                ? { ...t, output: result.output, isError: result.is_error, done: true }
                : t
            )
          )
        },
        onActionRequired(action) { setPendingAction(action) },
        onError(message) {
          setMessages((m) => [
            ...m,
            {
              id: crypto.randomUUID(),
              role: 'assistant',
              content: `**Erro:** ${message}`,
              created_at: new Date().toISOString(),
            },
          ])
        },
        signal: ctrl.signal,
      })
      setPendingText('')
      setPendingTools([])
      const msgs = await fetchMessages(token, c.id)
      setMessages(msgs)
    } catch (e) {
      if (e instanceof AuthError) {
        setToken(null); window.location.href = '/login'; return
      } else if (e instanceof Error && e.name === 'AbortError') {
        // Cancelled by user — silently finalize
      } else {
        setMessages((m) => [
          ...m,
          {
            id: crypto.randomUUID(),
            role: 'assistant',
            content: `**Erro:** ${e instanceof Error ? e.message : String(e)}`,
            created_at: new Date().toISOString(),
          },
        ])
      }
    } finally {
      setStreaming(false)
      abortControllerRef.current = null
      fetchConversationDiff(token, c.id).then((d) => setDiffStats(d.stats)).catch(() => {})
    }
  }

  async function handleSend(textOverride?: string) {
    const text = (textOverride ?? input).trim()
    if (!text || !activeId || streaming) return

    if (!textOverride) setInput('')
    setStreaming(true)
    setPendingText('')
    setPendingTools([])
    setPendingAction(null)

    const ctrl = new AbortController()
    abortControllerRef.current = ctrl

    const userMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content: text,
      created_at: new Date().toISOString(),
    }
    setMessages((m) => [...m, userMsg])

    try {
      await streamAssistantReply(token, activeId, text, {
        onText(accumulated) { setPendingText(accumulated) },
        onToolStart(tool) {
          setPendingTools((prev) => [
            ...prev,
            { id: tool.id, name: tool.name, input: tool.input, done: false },
          ])
        },
        onToolResult(result) {
          setPendingTools((prev) =>
            prev.map((t) =>
              t.id === result.id
                ? { ...t, output: result.output, isError: result.is_error, done: true }
                : t
            )
          )
        },
        onActionRequired(action) { setPendingAction(action) },
        onError(message) {
          setMessages((m) => [
            ...m,
            {
              id: crypto.randomUUID(),
              role: 'assistant',
              content: `**Erro:** ${message}`,
              created_at: new Date().toISOString(),
            },
          ])
        },
        signal: ctrl.signal,
      })
      setPendingText('')
      setPendingTools([])
      const msgs = await fetchMessages(token, activeId)
      setMessages(msgs)
    } catch (e) {
      if (e instanceof AuthError) {
        setToken(null); window.location.href = '/login'; return
      } else if (e instanceof Error && e.name === 'AbortError') {
        // Cancelled by user — silently finalize
      } else {
        setMessages((m) => [
          ...m,
          {
            id: crypto.randomUUID(),
            role: 'assistant',
            content: `**Erro:** ${e instanceof Error ? e.message : String(e)}`,
            created_at: new Date().toISOString(),
          },
        ])
      }
    } finally {
      setStreaming(false)
      abortControllerRef.current = null
      if (activeId) fetchConversationDiff(token, activeId).then((d) => setDiffStats(d.stats)).catch(() => {})
    }
  }

  function handleActionReply(reply: string) { handleSend(reply) }

  function logout() {
    setToken(null)
    window.location.reload()
  }

  const activeConv = conversations.find((c) => c.id === activeId)
  const activeEnvSlug = activeConv?.env_slug ?? null
  const showThinking =
    streaming && !pendingText && pendingTools.every((t) => t.done) && !pendingAction

  const groups = groupConversations(conversations)

  if (loading) {
    return (
      <div className={styles.loadingWrapper}>
        <ThinkingIndicator />
      </div>
    )
  }

  return (
    <div className={styles.shell}>
      <div className={styles.body}>
        {/* ── Sidebar ──────────────────────────────────────────── */}
        <aside className={`${styles.sidebar} ${mobileOpened ? styles.sidebarOpen : ''}`}>
          {/* Sidebar header */}
          <div className={styles.sidebarHead}>
            <div className={styles.sidebarHeadLeft}>
              <img src="/capybara.png" alt="" className={styles.sidebarLogo} />
              <div>
                <div className={styles.sidebarTitle}>CappyCloud</div>
                <div className={styles.sidebarSubtitle}>Research Preview</div>
              </div>
            </div>
            <Burger
              opened={mobileOpened}
              onClick={toggleMobile}
              size="sm"
              color="var(--cc-on-surface-variant)"
              hiddenFrom="sm"
            />
          </div>

          {/* New session button */}
          <div className={styles.sidebarActions}>
            <button className={styles.newSessionBtn} onClick={handleNewChat}>
              <span className={styles.icon}>add</span>
              <span>Nova Sessão</span>
              <span className={styles.kbdHint}>⌘N</span>
            </button>
          </div>

          {/* Session list */}
          <div className={styles.sessionList}>
            {groups.length === 0 && (
              <p className={styles.emptyHint}>Nenhuma conversa ainda.</p>
            )}
            {groups.map((g) => (
              <section key={g.label}>
                <h3 className={styles.groupLabel}>{g.label}</h3>
                <div className={styles.groupItems}>
                  {g.items.map((c) => (
                    <button
                      key={c.id}
                      className={`${styles.sessionItem} ${c.id === activeId ? styles.sessionItemActive : ''}`}
                      onClick={() => setActiveId(c.id)}
                    >
                      <span className={`${styles.icon} ${styles.sessionIcon}`}>
                        chat_bubble
                      </span>
                      <span className={styles.sessionLabel}>{c.title}</span>
                      {c.env_slug && (
                        <span className={styles.sessionEnvDot} title={c.env_slug} />
                      )}
                    </button>
                  ))}
                </div>
              </section>
            ))}
          </div>

          {/* Sidebar bottom nav */}
          <div className={styles.sidebarNav}>
            <Link to="/settings" className={styles.sidebarNavItem} title="Configurações">
              <span className={styles.icon}>settings</span>
              <span>Configurações</span>
            </Link>
            <button className={styles.sidebarNavItem} onClick={logout} title="Sair">
              <span className={styles.icon}>logout</span>
              <span>Sair</span>
            </button>
          </div>
        </aside>

        {/* ── Main ─────────────────────────────────────────────── */}
        <main className={styles.main}>
          {!activeId ? (
          <EmptyState
            input={input}
            setInput={setInput}
            inputRef={inputRef}
            onExecute={(text) => handleNewChatWithMessage(text)}
            streaming={streaming}
            workspaces={workspaces}
            selectedSlug={selectedSlug}
            setSelectedSlug={setSelectedSlug}
            selectedBranch={selectedBranch}
            setSelectedBranch={setSelectedBranch}
            token={token}
          />
          ) : (
            <ActiveChat
              messages={messages}
              pendingText={pendingText}
              pendingTools={pendingTools}
              pendingAction={pendingAction}
              showThinking={showThinking}
              streaming={streaming}
              input={input}
              setInput={setInput}
              inputRef={inputRef}
              onSend={() => handleSend()}
              onStop={handleStop}
              onActionReply={handleActionReply}
              activeEnvSlug={activeEnvSlug}
              activeEnvName={workspaces.find(w => w.slug === activeEnvSlug)?.name ?? activeEnvSlug ?? workspaces[0]?.name ?? null}
              activeBaseBranch={activeConv?.base_branch ?? null}
              workspaces={workspaces}
              diffStats={diffStats}
              prLoading={prLoading}
              prUrl={prUrl}
              headBranch={headBranch}
              onCreatePr={handleCreatePr}
              activeTitle={activeConv?.title ?? 'Conversa'}
              token={token}
              conversationId={activeId!}
              sidePanel={sidePanel}
              diff={diff}
              diffLoading={diffLoading}
              onOpenDiff={handleOpenDiff}
              onToggleFiles={handleToggleFiles}
            />
          )}
        </main>
      </div>
    </div>
  )
}

/* ────────────────────────────────────────────────────────────────
   Empty State — command bar premium centralizada
   ──────────────────────────────────────────────────────────────── */
interface EmptyStateProps {
  input: string
  setInput: (v: string) => void
  inputRef: React.RefObject<HTMLTextAreaElement | null>
  onExecute: (text: string) => void
  streaming: boolean
  workspaces: Workspace[]
  selectedSlug: string
  setSelectedSlug: (s: string) => void
  selectedBranch: string
  setSelectedBranch: (b: string) => void
  token: string
}

function EmptyState({
  input, setInput, inputRef, onExecute, streaming,
  workspaces, selectedSlug, setSelectedSlug,
  selectedBranch, setSelectedBranch, token,
}: EmptyStateProps) {
  const [branches, setBranches] = useState<string[]>([])
  const [loadedSlug, setLoadedSlug] = useState('')
  const branchesLoading = !!selectedSlug && loadedSlug !== selectedSlug

  // auto-clone trata o caso de repo não clonado
  const canExecute = !!selectedSlug && !!selectedBranch && !!input.trim() && !streaming

  useEffect(() => {
    if (!selectedSlug) return
    let cancelled = false
    fetchBranches(token, selectedSlug).then(({ branches: list, default: def }) => {
      if (cancelled) return
      setBranches(list)
      setLoadedSlug(selectedSlug)
      setSelectedBranch((prev) => (list.includes(prev) ? prev : def))
    })
    return () => { cancelled = true }
  }, [selectedSlug, token, setSelectedBranch])

  function handleKey(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey && !streaming) {
      e.preventDefault()
      if (canExecute) onExecute(input)
    }
  }

  const repoRequired = workspaces.length > 0 && !selectedSlug
  const branchRequired = !!selectedSlug && !selectedBranch

  return (
    <div className={styles.emptyState}>
      {/* Mascot */}
      <div className={styles.mascotWrapper}>
        <img src="/capybara.png" alt="CappyCloud" className={styles.mascot} />
        <div className={styles.mascotGlow} />
      </div>

      {/* Premium Command Bar */}
      <div className={styles.commandBarWrapper}>
        <div className={styles.commandBarGlow} />
        <div className={styles.commandBar}>
          <div className={styles.commandBarInner}>
            <div className={styles.commandInputRow}>
              <span className={`${styles.icon} ${styles.boltIcon}`}>bolt</span>
              <textarea
                ref={inputRef}
                className={styles.commandTextarea}
                placeholder={
                  !selectedSlug
                    ? 'Selecione um repositório e branch antes de continuar…'
                    : !selectedBranch
                      ? 'Selecione uma branch antes de continuar…'
                      : 'Descreva o que o agente deve fazer…'
                }
                rows={2}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKey}
                disabled={!selectedSlug || !selectedBranch}
              />
            </div>

            <div className={styles.commandToolbar}>
              <div className={styles.commandToolbarLeft}>
                <button className={styles.toolbarBtn} title="Anexar" disabled={!selectedSlug || !selectedBranch}>
                  <span className={styles.icon}>attachment</span>
                </button>
                {workspaces.length > 0 ? (
                  <div
                    className={`${styles.contextPill} ${repoRequired ? styles.contextPillRequired : ''}`}
                    style={{ marginLeft: '0.5rem' }}
                  >
                    <span className={styles.icon} style={{ fontSize: '0.875rem', opacity: 0.6 }}>
                      source
                    </span>
                    <span className={styles.contextPillLabel} style={!selectedSlug ? { opacity: 0.45 } : undefined}>
                      {workspaces.find(w => w.slug === selectedSlug)?.name ?? 'Repositório…'}
                    </span>
                    <span className={styles.icon} style={{ fontSize: '0.75rem', opacity: 0.35 }}>
                      expand_more
                    </span>
                    <select
                      className={styles.contextPillSelect}
                      value={selectedSlug}
                      onChange={(e) => setSelectedSlug(e.target.value)}
                      title="Selecionar repositório"
                    >
                      {!selectedSlug && (
                        <option value="" disabled>Selecionar repositório…</option>
                      )}
                      {workspaces.map((w) => (
                        <option key={w.slug} value={w.slug}>{w.name}</option>
                      ))}
                    </select>
                  </div>
                ) : (
                  <div className={`${styles.contextPill} ${styles.contextPillRequired}`} style={{ marginLeft: '0.5rem' }}>
                    <span className={styles.icon} style={{ fontSize: '0.875rem', opacity: 0.5 }}>source</span>
                    <span className={styles.contextPillLabel} style={{ opacity: 0.45 }}>Nenhum repositório</span>
                  </div>
                )}
                {selectedSlug && (
                  <div
                    className={`${styles.contextPill} ${branchRequired ? styles.contextPillRequired : ''}`}
                    style={{ marginLeft: '0.25rem' }}
                  >
                    <span className={styles.icon} style={{ fontSize: '0.875rem', opacity: 0.6 }}>
                      fork_right
                    </span>
                    <span className={styles.contextPillLabel} style={!selectedBranch ? { opacity: 0.45 } : undefined}>
                      {branchesLoading ? '…' : (selectedBranch || 'Branch…')}
                    </span>
                    <span className={styles.icon} style={{ fontSize: '0.75rem', opacity: 0.35 }}>
                      expand_more
                    </span>
                    <select
                      className={styles.contextPillSelect}
                      value={selectedBranch}
                      onChange={(e) => setSelectedBranch(e.target.value)}
                      disabled={branchesLoading}
                      title="Selecionar branch"
                    >
                      {!selectedBranch && !branchesLoading && (
                        <option value="" disabled>Selecionar branch…</option>
                      )}
                      {branches.map((b) => (
                        <option key={b} value={b}>{b}</option>
                      ))}
                    </select>
                  </div>
                )}
              </div>

              <div className={styles.commandToolbarRight}>
                <button
                  className={styles.executeBtn}
                  onClick={() => canExecute && onExecute(input)}
                  disabled={!canExecute}
                  title={
                    !selectedSlug ? 'Selecione um repositório' :
                    !selectedBranch ? 'Selecione uma branch' :
                    !input.trim() ? 'Digite uma mensagem' : undefined
                  }
                >
                  <span>Executar</span>
                  <span className={styles.icon}>keyboard_return</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Quick Actions */}
      <div className={styles.quickActions}>
        <QuickActionCard
          icon="terminal"
          iconColor="var(--cc-secondary)"
          title="Terminal Local"
          desc="Acesse o shell nativo com atalhos contextuais."
        />
        <QuickActionCard
          icon="search_check"
          iconColor="var(--cc-primary)"
          title="Auditoria de Código"
          desc="Escaneie vulnerabilidades e dívida arquitetural."
        />
        <QuickActionCard
          icon="history"
          iconColor="var(--cc-error)"
          title="Replay de Sessão"
          desc="Revise decisões arquiteturais anteriores."
        />
      </div>
    </div>
  )
}

function QuickActionCard({ icon, iconColor, title, desc }: {
  icon: string; iconColor: string; title: string; desc: string
}) {
  return (
    <div className={styles.quickCard}>
      <div className={styles.quickCardHeader}>
        <span className={styles.icon} style={{ color: iconColor }}>{icon}</span>
        <span className={styles.quickCardTitle}>{title}</span>
      </div>
      <p className={styles.quickCardDesc}>{desc}</p>
    </div>
  )
}

/* ────────────────────────────────────────────────────────────────
   Active Chat — mensagens + input compacto
   ──────────────────────────────────────────────────────────────── */
interface ActiveChatProps {
  messages: ChatMessage[]
  pendingText: string
  pendingTools: ToolCallState[]
  pendingAction: ActionRequiredEvent | null
  showThinking: boolean
  streaming: boolean
  input: string
  setInput: (v: string) => void
  inputRef: React.RefObject<HTMLTextAreaElement | null>
  onSend: () => void
  onStop: () => void
  onActionReply: (r: string) => void
  activeEnvSlug: string | null
  activeEnvName: string | null
  activeBaseBranch: string | null
  workspaces: Workspace[]
  diffStats: { added: number; removed: number } | null
  prLoading: boolean
  prUrl: string | null
  headBranch: string | null
  onCreatePr: () => void
  activeTitle: string
  token: string
  conversationId: string
  sidePanel: 'none' | 'diff' | 'files'
  diff: ConversationDiff | null
  diffLoading: boolean
  onOpenDiff: () => void
  onToggleFiles: () => void
}

function ActiveChat({
  messages, pendingText, pendingTools, pendingAction,
  showThinking, streaming, input, setInput, inputRef,
  onSend, onStop, onActionReply, activeEnvSlug, activeEnvName, activeBaseBranch,
  workspaces,
  diffStats, prLoading, prUrl, headBranch, onCreatePr,
  activeTitle: _activeTitle,
  token, conversationId, sidePanel, diff, diffLoading, onOpenDiff, onToggleFiles,
}: ActiveChatProps) {
  const scrollRef = useRef<HTMLDivElement>(null)
  const [elapsedSecs, setElapsedSecs] = useState(0)

  useEffect(() => {
    setElapsedSecs(0)
    if (!streaming) return
    const id = setInterval(() => setElapsedSecs((s) => s + 1), 1000)
    return () => clearInterval(id)
  }, [streaming])

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
    }
  }, [messages, pendingText, pendingTools, pendingAction, streaming])

  return (
    <div className={styles.activeChat}>
      {/* Session header — env + branch + diff stats + Criar PR */}
      {activeEnvSlug && (
        <div className={styles.sessionHeader}>
          <div className={styles.sessionHeaderLeft}>
            <span className={`${styles.icon} ${styles.sessionHeaderIcon}`}>source</span>
            <span className={styles.sessionHeaderEnv}>{activeEnvName ?? activeEnvSlug}</span>
            {activeBaseBranch && (
              <>
                <span className={styles.sessionHeaderArrow}>›</span>
                <span className={styles.sessionHeaderBranch}>
                  {headBranch ?? activeBaseBranch}
                </span>
              </>
            )}
          </div>
          <div className={styles.sessionHeaderRight}>
            {diffStats && (diffStats.added > 0 || diffStats.removed > 0) && (
              <>
                <span className={styles.diffAdded}>+{diffStats.added}</span>
                <span className={styles.diffRemoved}>-{diffStats.removed}</span>
                {prUrl ? (
                  <a
                    href={prUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className={styles.prLink}
                  >
                    <span className={`${styles.icon}`} style={{ fontSize: '0.875rem' }}>open_in_new</span>
                    Ver PR
                  </a>
                ) : (
                  <button
                    className={styles.createPrBtn}
                    onClick={onCreatePr}
                    disabled={prLoading || streaming}
                  >
                    {prLoading ? 'Criando…' : 'Criar PR'}
                  </button>
                )}
              </>
            )}
            <div className={styles.sessionHeaderPanelBtns}>
              <button
                className={`${styles.chatContextIconBtn} ${sidePanel === 'files' ? styles.chatContextIconBtnActive : ''}`}
                onClick={onToggleFiles}
                title="Explorador de ficheiros"
              >
                <span className={styles.icon}>folder_open</span>
              </button>
              <button
                className={`${styles.chatContextIconBtn} ${sidePanel === 'diff' ? styles.chatContextIconBtnActive : ''}`}
                onClick={onOpenDiff}
                title="Ver diff"
              >
                <span className={styles.icon}>difference</span>
              </button>
            </div>
          </div>
        </div>
      )}
      <div className={styles.chatBody}>
        {/* Messages column */}
        <div className={styles.chatMessages}>
          <ScrollArea className={styles.messageArea} viewportRef={scrollRef} type="auto">
            <Stack gap="sm" p="md">
              {messages.map((m) => (
                <PaperMessage key={m.id} role={m.role} content={m.content} />
              ))}

              {streaming && (
                <Stack gap="xs">
                  {pendingTools.map((tool) => (
                    <ToolCallCard key={tool.id} tool={tool} />
                  ))}
                  {(showThinking || (streaming && pendingTools.some(t => !t.done))) && (
                    <ThinkingIndicator label={pendingTools.some(t => !t.done) ? 'A executar…' : undefined} />
                  )}
                  {pendingText && (
                    <PaperMessage role="assistant" content={pendingText} streaming />
                  )}
                </Stack>
              )}

              {pendingAction && (
                <ActionRequiredCard action={pendingAction} onReply={onActionReply} />
              )}
            </Stack>
          </ScrollArea>
        </div>

        {/* Side panel */}
        {sidePanel !== 'none' && (
          <div className={styles.sidePanel}>
            {sidePanel === 'diff' && (
              diffLoading
                ? <div className={styles.sidePanelLoading}><Text size="xs" c="dimmed">A carregar diff…</Text></div>
                : diff
                  ? <DiffViewer diff={diff} />
                  : <div className={styles.sidePanelLoading}><Text size="xs" c="dimmed">Sem diff disponível</Text></div>
            )}
            {sidePanel === 'files' && (
              <FileExplorer token={token} conversationId={conversationId} />
            )}
          </div>
        )}
      </div>

      {/* Compact input bar */}
      <div className={styles.chatInputBar}>
        <div className={styles.chatInputWrapper}>
          <textarea
            ref={inputRef}
            className={styles.chatTextarea}
            placeholder="Mensagem ao agente… (Enter para enviar)"
            rows={2}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey && !streaming) {
                e.preventDefault()
                onSend()
              }
            }}
            disabled={streaming && !pendingAction}
          />
          {streaming ? (
            <button className={styles.stopBtn} onClick={onStop} title="Parar agente">
              <span className={styles.icon}>stop</span>
              <span className={styles.stopBtnTimer}>{elapsedSecs}s</span>
            </button>
          ) : (
          <button
            className={styles.sendBtn}
            onClick={onSend}
            disabled={(!input.trim() && !pendingAction) || (streaming && !pendingAction)}
          >
            <span className={styles.icon}>keyboard_return</span>
          </button>
          )}
        </div>

        {/* Context status bar — repo pill */}
        <div className={styles.chatContextBar}>
          <div className={styles.chatContextPill}>
            <span className={`${styles.icon} ${styles.chatContextIcon}`}>source</span>
            <span className={styles.chatContextText}>
              {activeEnvName ?? activeEnvSlug ?? workspaces[0]?.name ?? '—'}
            </span>
            {workspaces.length > 1 && (
              <>
                <span className={styles.icon} style={{ fontSize: '0.75rem', opacity: 0.35 }}>expand_more</span>
                <select
                  className={styles.contextPillSelect}
                  value={activeEnvSlug ?? workspaces[0]?.slug ?? ''}
                  disabled
                  title="Repo da conversa (definido ao criar)"
                >
                  {workspaces.map((w) => (
                    <option key={w.slug} value={w.slug}>{w.name}</option>
                  ))}
                </select>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

/* ────────────────────────────────────────────────────────────────
   Message bubble
   ──────────────────────────────────────────────────────────────── */
function PaperMessage({ role, content, streaming }: { role: string; content: string; streaming?: boolean }) {
  const isUser = role === 'user'
  return (
    <div className={`${styles.message} ${isUser ? styles.messageUser : styles.messageAgent}`}>
      <Text
        size="xs"
        mb={4}
        style={{
          color: isUser ? 'rgba(255,255,255,0.55)' : 'var(--cc-on-surface-variant)',
          fontFamily: 'Space Grotesk, sans-serif',
          fontWeight: 600,
          letterSpacing: '0.06em',
          textTransform: 'uppercase',
          fontSize: '0.6rem',
        }}
      >
        {isUser ? 'Tu' : 'Agente'}
      </Text>
      {isUser ? (
        <Text
          size="sm"
          style={{
            color: '#fff',
            fontFamily: 'Inter, sans-serif',
            lineHeight: 1.6,
            whiteSpace: 'pre-wrap',
          }}
        >
          {content}
        </Text>
      ) : (
        <div className={styles.markdownBody}>
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
          {streaming && <span className={styles.streamingCursor} aria-hidden />}
        </div>
      )}
    </div>
  )
}
