import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Burger,
  Button,
  ScrollArea,
  Stack,
  Text,
} from '@mantine/core'
import { useDisclosure } from '@mantine/hooks'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import {
  cancelConversation,
  createConversation,
  fetchConversationDiff,
  fetchConversations,
  fetchMessages,
  fetchRepoEnvironments,
  getToken,
  setToken,
  streamAssistantReply,
  type ActionRequiredEvent,
  type ChatMessage,
  type Conversation,
  type ConversationDiff,
  type RepoEnv,
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

  const [envs, setEnvs] = useState<RepoEnv[]>([])
  const [selectedEnvId, setSelectedEnvId] = useState<string | null>(null)
  const [selectedBranch, setSelectedBranch] = useState<string>('')

  const [pendingText, setPendingText] = useState('')
  const [pendingTools, setPendingTools] = useState<ToolCallState[]>([])
  const [pendingAction, setPendingAction] = useState<ActionRequiredEvent | null>(null)

  const [sidePanel, setSidePanel] = useState<'none' | 'diff' | 'files'>('none')
  const [diff, setDiff] = useState<ConversationDiff | null>(null)
  const [diffLoading, setDiffLoading] = useState(false)

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
        const [list, envList] = await Promise.all([
          fetchConversations(token),
          fetchRepoEnvironments(token),
        ])
        if (cancelled) return
        setConversations(list)
        setEnvs(envList)
        if (list.length > 0) setActiveId((prev) => prev ?? list[0].id)
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => { cancelled = true }
  }, [token])

  useEffect(() => {
    if (!activeId) return
    let cancelled = false
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

  async function handleNewChat() {
    const c = await createConversation(token, selectedEnvId, selectedBranch || null)
    setConversations((prev) => [c, ...prev])
    setActiveId(c.id)
    setMessages([])
    setTimeout(() => inputRef.current?.focus(), 50)
  }

  /** Cria conversa e envia a mensagem inicial de uma vez */
  async function handleNewChatWithMessage(text: string) {
    if (!text.trim()) return
    const c = await createConversation(token, selectedEnvId, selectedBranch || null)
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
      if (e instanceof Error && e.name === 'AbortError') {
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
      if (e instanceof Error && e.name === 'AbortError') {
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

  const selectedEnv = envs.find((e) => e.id === selectedEnvId)

  // Quando o ambiente selecionado muda, resetar selectedBranch para o branch padrão do env
  useEffect(() => {
    setSelectedBranch(selectedEnv?.branch ?? '')
  }, [selectedEnvId, selectedEnv?.branch])

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
      {/* ── Top Bar ────────────────────────────────────────────── */}
      <header className={styles.topbar}>
        <div className={styles.topbarLeft}>
          <Burger
            opened={mobileOpened}
            onClick={toggleMobile}
            size="sm"
            color="var(--cc-on-surface-variant)"
            hiddenFrom="sm"
          />
          <img src="/capybara.png" alt="" className={styles.topbarLogo} />
          <span className={styles.topbarTitle}>CappyCloud</span>
          <span className={styles.topbarBadge}>Beta</span>
        </div>
        <div className={styles.topbarRight}>
          <Button
            component={Link}
            to="/environments"
            variant="subtle"
            size="xs"
            color="gray"
            className={styles.topbarBtn}
          >
            Ambientes
          </Button>
          <button className={styles.topbarIconBtn} onClick={logout} title="Sair">
            <span className={styles.icon}>logout</span>
          </button>
        </div>
      </header>

      <div className={styles.body}>
        {/* ── Sidebar ──────────────────────────────────────────── */}
        <aside className={`${styles.sidebar} ${mobileOpened ? styles.sidebarOpen : ''}`}>
          {/* Sidebar header */}
          <div className={styles.sidebarHead}>
            <div>
              <div className={styles.sidebarTitle}>CappyCloud</div>
              <div className={styles.sidebarSubtitle}>Research Preview</div>
            </div>
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

          {/* Sessão ativa — ambiente em uso */}
          {activeId && (
            <div className={styles.activeEnvBanner}>
              <span className={styles.icon} style={{ fontSize: '0.875rem', color: activeEnvSlug ? 'var(--cc-secondary)' : 'var(--cc-on-surface-variant)' }}>
                {activeEnvSlug ? 'check_circle' : 'radio_button_unchecked'}
              </span>
              <div className={styles.activeEnvMeta}>
                <span className={styles.activeEnvLabel}>Sessão atual</span>
                <span className={styles.activeEnvValue}>
                  {activeEnvSlug
                    ? envs.find(e => e.slug === activeEnvSlug)?.name ?? activeEnvSlug
                    : 'Sem ambiente'}
                </span>
              </div>
            </div>
          )}

          {/* Sidebar footer — seletor de ambiente e branch */}
          <div className={styles.sidebarFooter}>
            <p className={styles.footerLabel}>Próxima sessão</p>

            {/* Seletor de repositório */}
            <div className={styles.sessionPickerRow}>
              <div className={styles.sessionPickerIcon}>
                <img src="/capybara.png" alt="" />
              </div>
              <div className={styles.sessionPickerMeta}>
                <span className={styles.sessionPickerLabel}>Repositório</span>
                <span className={styles.sessionPickerValue}>
                  {selectedEnv?.name ?? 'Sem ambiente'}
                </span>
              </div>
              <span className={styles.icon} style={{ fontSize: '1rem', opacity: 0.4, marginLeft: 'auto' }}>
                expand_more
              </span>
              <select
                className={styles.envSelectorNative}
                value={selectedEnvId ?? ''}
                onChange={(e) => setSelectedEnvId(e.target.value || null)}
                title="Selecionar repositório"
              >
                <option value="">Sem ambiente</option>
                {envs.map((e) => (
                  <option key={e.id} value={e.id}>
                    {e.name} ({e.slug})
                  </option>
                ))}
              </select>
            </div>

            {/* Seletor de branch */}
            <div className={`${styles.sessionPickerRow} ${!selectedEnvId ? styles.sessionPickerDisabled : ''}`}>
              <span className={`${styles.icon} ${styles.sessionPickerBranchIcon}`}>
                fork_right
              </span>
              <div className={styles.sessionPickerMeta}>
                <span className={styles.sessionPickerLabel}>Branch de origem</span>
                <input
                  className={styles.branchInput}
                  type="text"
                  value={selectedBranch}
                  onChange={(e) => setSelectedBranch(e.target.value)}
                  placeholder={selectedEnv?.branch ?? 'main'}
                  disabled={!selectedEnvId}
                  spellCheck={false}
                  title="Branch base para a sessão"
                />
              </div>
            </div>
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
            envs={envs}
            selectedEnvId={selectedEnvId}
            setSelectedEnvId={setSelectedEnvId}
            selectedBranch={selectedBranch}
            streaming={streaming}
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
              envs={envs}
              activeTitle={activeConv?.title ?? 'Conversa'}
              selectedEnvId={selectedEnvId}
              setSelectedEnvId={setSelectedEnvId}
              selectedBranch={selectedBranch}
              setSelectedBranch={setSelectedBranch}
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
  inputRef: React.RefObject<HTMLTextAreaElement>
  onExecute: (text: string) => void
  envs: RepoEnv[]
  selectedEnvId: string | null
  setSelectedEnvId: (id: string | null) => void
  selectedBranch: string
  streaming: boolean
}

function EmptyState({
  input, setInput, inputRef, onExecute,
  envs, selectedEnvId, setSelectedEnvId, selectedBranch, streaming,
}: EmptyStateProps) {
  const selectedEnv = envs.find((e) => e.id === selectedEnvId)

  function handleKey(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey && !streaming) {
      e.preventDefault()
      if (input.trim()) onExecute(input)
    }
  }

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
                placeholder="Descreva o que o agente deve fazer…"
                rows={2}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKey}
              />
            </div>

            <div className={styles.commandToolbar}>
              <div className={styles.commandToolbarLeft}>
                <button className={styles.toolbarBtn} title="Anexar">
                  <span className={styles.icon}>attachment</span>
                </button>
              </div>

              <div className={styles.commandToolbarRight}>
                <button
                  className={styles.executeBtn}
                  onClick={() => onExecute(input)}
                  disabled={!input.trim() || streaming}
                >
                  <span>Executar</span>
                  <span className={styles.icon}>keyboard_return</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Context Bar — igual ao Stitch */}
      <div className={styles.contextBar}>
        {/* Env pill — select nativo embutido */}
        <div className={styles.contextPill} title="Selecionar ambiente">
          <span className={styles.icon} style={{ fontSize: '0.875rem', opacity: 0.6 }}>
            inventory_2
          </span>
          <span className={styles.contextPillLabel}>
            {selectedEnv?.name ?? 'Sem ambiente'}
          </span>
          <span className={styles.icon} style={{ fontSize: '0.75rem', opacity: 0.35 }}>
            expand_more
          </span>
          <select
            className={styles.contextPillSelect}
            value={selectedEnvId ?? ''}
            onChange={(e) => setSelectedEnvId(e.target.value || null)}
            title="Selecionar ambiente"
          >
            <option value="">Sem ambiente</option>
            {envs.map((e) => (
              <option key={e.id} value={e.id}>
                {e.name} ({e.slug})
              </option>
            ))}
          </select>
        </div>

        {/* Branch pill */}
        {selectedEnv && (
          <div className={styles.contextPill}>
            <span className={styles.icon} style={{ fontSize: '0.875rem', opacity: 0.6 }}>
              fork_right
            </span>
            <span className={styles.contextPillLabel}>{selectedBranch || selectedEnv.branch}</span>
          </div>
        )}

        {/* Add env */}
        <Link to="/environments" className={styles.contextPillAdd} title="Adicionar ambiente">
          <span className={styles.icon} style={{ fontSize: '1rem' }}>add</span>
        </Link>
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
  inputRef: React.RefObject<HTMLTextAreaElement>
  onSend: () => void
  onStop: () => void
  onActionReply: (r: string) => void
  activeEnvSlug: string | null
  activeTitle: string
  envs: RepoEnv[]
  selectedEnvId: string | null
  setSelectedEnvId: (id: string | null) => void
  selectedBranch: string
  setSelectedBranch: (v: string) => void
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
  onSend, onStop, onActionReply, activeEnvSlug, activeTitle, envs,
  selectedEnvId, setSelectedEnvId, selectedBranch, setSelectedBranch,
  token, conversationId, sidePanel, diff, diffLoading, onOpenDiff, onToggleFiles,
}: ActiveChatProps) {
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
    }
  }, [messages, pendingText, pendingTools, pendingAction, streaming])

  return (
    <div className={styles.activeChat}>
      {/* Chat title bar */}
      <div className={styles.chatTitleBar}>
        <span className={styles.chatTitle}>{activeTitle}</span>
        <div className={styles.chatTitleEnv}>
          <span className={styles.icon} style={{ fontSize: '0.875rem', color: activeEnvSlug ? 'var(--cc-secondary)' : 'var(--cc-on-surface-variant)', opacity: activeEnvSlug ? 1 : 0.4 }}>
            inventory_2
          </span>
          <span className={activeEnvSlug ? styles.chatTitleEnvActive : styles.chatTitleEnvEmpty}>
            {activeEnvSlug
              ? (envs.find(e => e.slug === activeEnvSlug)?.name ?? activeEnvSlug)
              : 'Sem ambiente'}
          </span>
        </div>
        {/* Panel buttons */}
        <div className={styles.chatTitleActions}>
          {activeEnvSlug && (
            <>
              <button
                className={`${styles.panelBtn} ${sidePanel === 'files' ? styles.panelBtnActive : ''}`}
                onClick={onToggleFiles}
                title="Explorador de ficheiros"
              >
                <span className={styles.icon}>folder_open</span>
                <span>Ficheiros</span>
              </button>
              <button
                className={`${styles.panelBtn} ${sidePanel === 'diff' ? styles.panelBtnActive : ''}`}
                onClick={onOpenDiff}
                title="Ver diff"
              >
                <span className={styles.icon}>difference</span>
                <span>Diff</span>
              </button>
            </>
          )}
        </div>
      </div>

      {/* Body: messages + optional side panel */}
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
                  {showThinking && <ThinkingIndicator />}
                  {pendingText && <PaperMessage role="assistant" content={pendingText} />}
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

        {/* Context status bar — repo + branch selector */}
        <div className={styles.chatContextBar}>
          {/* Repo selector */}
          <div className={styles.chatContextPill}>
            <span className={`${styles.icon} ${styles.chatContextIcon}`}>inventory_2</span>
            <span className={styles.chatContextText}>
              {envs.find(e => e.id === selectedEnvId)?.name ?? 'Sem ambiente'}
            </span>
            <span className={`${styles.icon} ${styles.chatContextChevron}`}>expand_more</span>
            <select
              className={styles.chatContextSelect}
              value={selectedEnvId ?? ''}
              onChange={(e) => setSelectedEnvId(e.target.value || null)}
              title="Selecionar repositório"
            >
              <option value="">Sem ambiente</option>
              {envs.map((e) => (
                <option key={e.id} value={e.id}>
                  {e.name} ({e.slug})
                </option>
              ))}
            </select>
          </div>

          <span className={styles.chatContextSep}>›</span>

          {/* Branch selector */}
          <div className={styles.chatContextPill}>
            <span className={`${styles.icon} ${styles.chatContextIcon}`}>fork_right</span>
            <input
              className={styles.chatContextBranchInput}
              type="text"
              value={selectedBranch}
              onChange={(e) => setSelectedBranch(e.target.value)}
              placeholder={envs.find(e => e.id === selectedEnvId)?.branch ?? 'main'}
              spellCheck={false}
              title="Branch de origem da próxima sessão"
            />
          </div>
        </div>
      </div>
    </div>
  )
}

/* ────────────────────────────────────────────────────────────────
   Message bubble
   ──────────────────────────────────────────────────────────────── */
function PaperMessage({ role, content }: { role: string; content: string }) {
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
        </div>
      )}
    </div>
  )
}
