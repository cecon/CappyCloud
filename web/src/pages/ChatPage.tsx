import { Fragment, type Dispatch, type SetStateAction, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import {
  Burger,
  ScrollArea,
  Stack,
  Text,
} from '@mantine/core'
import { useDisclosure } from '@mantine/hooks'
import ReactMarkdown, { type Components } from 'react-markdown'
import remarkGfm from 'remark-gfm'
import {
  AuthError,
  cancelConversation,
  createConversation,
  createConversationPr,
  deleteAttachment,
  fetchAiModels,
  fetchBranches,
  fetchConversationDiff,
  fetchConversations,
  fetchConversationUsage,
  fetchMessages,
  fetchWorkspaces,
  getToken,
  setToken,
  streamAssistantReply,
  uploadAttachment,
  errorToUserMessage,
  type ActionRequiredEvent,
  type AiModel,
  type ChatMessage,
  type Conversation,
  type ConversationDiff,
  type ConversationUsage,
  type DoneEvent,
  type StatusEvent,
  type Workspace,
} from '../api'
import { ActionRequiredCard } from '../components/ActionRequiredCard'
import { AttachmentTray, type TrayItem } from '../components/AttachmentTray'
import { DiffViewer } from '../components/DiffViewer'
import { FileExplorer } from '../components/FileExplorer'
import { ModelPicker } from '../components/ModelPicker'
import { ThinkingIndicator } from '../components/ThinkingIndicator'
import { ThinkingStream, type ThoughtStep } from '../components/ThinkingStream'
import styles from '../components/chat.module.css'

const ALLOWED_ATTACHMENT_MIME = new Set([
  'image/png',
  'image/jpeg',
  'image/jpg',
  'image/webp',
  'image/gif',
])
const MAX_ATTACHMENT_BYTES = 8 * 1024 * 1024

const STICKY_SCROLL_THRESHOLD_PX = 96

/**
 * Formata custo USD como "$0.0034" / "$1.20" / "free" / "—".
 * Sub-cêntimo recebe 4 casas para não colapsar a zero.
 */
function formatCostUsd(value: number | null | undefined): string {
  if (value == null) return '—'
  if (value === 0) return 'free'
  if (value < 0.01) return `$${value.toFixed(4)}`
  return `$${value.toFixed(2)}`
}

/**
 * Ordena modelos: free primeiro (melhor para experimentar), depois por preço de
 * input ascendente, com pricing desconhecido no fim. Estável por display_name.
 */
function sortModelsForSelect(models: AiModel[]): AiModel[] {
  const score = (m: AiModel) => {
    const ic = m.input_cost_per_1m_usd
    if (ic == null) return Number.POSITIVE_INFINITY
    return Number(ic)
  }
  return [...models].sort((a, b) => {
    const sa = score(a)
    const sb = score(b)
    if (sa !== sb) return sa - sb
    return a.display_name.localeCompare(b.display_name)
  })
}

/**
 * UUID v4 com fallback. `randomId()` só existe em contextos seguros
 * (HTTPS ou localhost). Em http://<IP>:porta o método é `undefined` e o React
 * estoura. Estes IDs são apenas chave React / id local de mensagem — não
 * precisam de aleatoriedade criptográfica quando o fallback é usado.
 */
function randomId(): string {
  const c = typeof crypto !== 'undefined' ? crypto : undefined
  if (c && typeof c.randomUUID === 'function') return c.randomUUID()
  if (c && typeof c.getRandomValues === 'function') {
    const b = c.getRandomValues(new Uint8Array(16))
    b[6] = (b[6] & 0x0f) | 0x40
    b[8] = (b[8] & 0x3f) | 0x80
    const h = Array.from(b, (x) => x.toString(16).padStart(2, '0')).join('')
    return `${h.slice(0, 8)}-${h.slice(8, 12)}-${h.slice(12, 16)}-${h.slice(16, 20)}-${h.slice(20)}`
  }
  return `id-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 11)}`
}

/** Agrupa conversas em Hoje / Ontem / Anteriores */
function groupConversations(convs: Conversation[]): { label: string; items: Conversation[] }[] {
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime()
  const yesterday = today - 86_400_000

  const groups: Record<string, Conversation[]> = { Hoje: [], Ontem: [], Anteriores: [] }
  for (const c of convs) {
    const d = new Date(c.created_at ?? c.id).getTime()
    if (d >= today) groups.Hoje.push(c)
    else if (d >= yesterday) groups.Ontem.push(c)
    else groups.Anteriores.push(c)
  }
  return Object.entries(groups)
    .filter(([, items]) => items.length > 0)
    .map(([label, items]) => ({ label, items }))
}

type SessionMode = 'initializing' | 'resuming'
type SessionStageKey = 'session' | 'repository' | 'ready' | 'agent'

type SessionStageState = {
  key: SessionStageKey
  label: string
  detail?: string
  status: 'pending' | 'active' | 'done'
}

type SessionProgressAnchor = {
  id: string
  content: string
}

const SESSION_STAGES: Array<{ key: SessionStageKey; label: string }> = [
  { key: 'session', label: 'Configurar contêiner na nuvem' },
  { key: 'repository', label: 'Repositório clonado' },
  { key: 'ready', label: 'Worktree da sessão criado' },
  { key: 'agent', label: 'Agente iniciado' },
]

const RESUMED_SESSION_STAGES: Array<{ key: SessionStageKey; label: string }> = [
  { key: 'session', label: 'Contêiner na nuvem reativado' },
  { key: 'repository', label: 'Repositório sincronizado' },
  { key: 'ready', label: 'Worktree da sessão reutilizado' },
  { key: 'agent', label: 'Agente reiniciado' },
]

/** Customiza elementos Markdown que precisam de comportamento visual ou seguro. */
const markdownComponents: Components = {
  a({ href, children, ...props }) {
    return (
      <a href={href} target="_blank" rel="noreferrer noopener" {...props}>
        {children}
      </a>
    )
  },
  table({ children, ...props }) {
    return (
      <div className={styles.markdownTableScroller}>
        <table {...props}>{children}</table>
      </div>
    )
  },
}

/** Devolve os rótulos corretos para sessão nova ou retomada. */
function sessionStagesForMode(mode: SessionMode): Array<{ key: SessionStageKey; label: string }> {
  return mode === 'resuming' ? RESUMED_SESSION_STAGES : SESSION_STAGES
}

/** Cria o estado inicial do checklist de inicialização da sessão. */
function createSessionProgress(mode: SessionMode = 'initializing'): SessionStageState[] {
  return sessionStagesForMode(mode).map((stage) => ({ ...stage, status: 'pending' }))
}

/** Marca etapas concluídas conforme eventos de progresso chegam do backend. */
function reduceSessionProgress(
  previous: SessionStageState[],
  event: StatusEvent,
): SessionStageState[] {
  const mode = event.mode ?? 'initializing'
  const stages = sessionStagesForMode(mode)
  const currentIndex = stages.findIndex((stage) => stage.key === event.stage)
  if (currentIndex < 0) return previous

  return previous.map((stage, index) => {
    const nextStage = stages[index] ?? stage
    if (index < currentIndex || event.stage === 'agent') {
      return { ...stage, label: nextStage.label, status: 'done' }
    }
    if (index === currentIndex) {
      return { ...stage, label: nextStage.label, status: 'active', detail: event.message }
    }
    return { ...stage, label: nextStage.label }
  })
}

/**
 * Timeline cronológica do "pensamento" do agente.
 * Concatena chunks de texto consecutivos no último step de tipo 'text' para
 * preservar a ordem natural texto→tool→texto→tool→… Quando chega um tool_start,
 * congela o texto atual e abre um novo step de tool. Tool_result actualiza o
 * step correspondente.
 */
function appendTextToThoughts(
  prev: ThoughtStep[],
  delta: string,
): ThoughtStep[] {
  if (!delta) return prev
  const last = prev[prev.length - 1]
  if (last && last.kind === 'text') {
    return [...prev.slice(0, -1), { ...last, content: last.content + delta }]
  }
  return [
    ...prev,
    { kind: 'text', id: `t-${prev.length}-${Date.now()}`, content: delta },
  ]
}

function appendToolStartToThoughts(
  prev: ThoughtStep[],
  tool: { id: string; name: string; input: string },
): ThoughtStep[] {
  if (prev.some((s) => s.kind === 'tool' && s.id === tool.id)) return prev
  return [
    ...prev,
    {
      kind: 'tool',
      id: tool.id,
      name: tool.name,
      input: tool.input,
      done: false,
    },
  ]
}

function applyToolResultToThoughts(
  prev: ThoughtStep[],
  result: { id: string; output: string; is_error: boolean },
): ThoughtStep[] {
  return prev.map((step) =>
    step.kind === 'tool' && step.id === result.id
      ? { ...step, output: result.output, isError: result.is_error, done: true }
      : step,
  )
}

/**
 * UI principal: layout IDE estilo "The Silent Architect".
 * Estado vazio → command bar premium centralizada.
 * Estado ativo  → lista de mensagens + input compacto.
 */
export function ChatPage() {
  const token = getToken()!
  const [mobileOpened, { toggle: toggleMobile, close: closeMobile }] = useDisclosure()

  const [conversations, setConversations] = useState<Conversation[]>([])
  const [activeId, setActiveId] = useState<string | null>(null)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [messagesLoading, setMessagesLoading] = useState(false)
  const [messagesError, setMessagesError] = useState<string | null>(null)
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [loading, setLoading] = useState(true)

  const [workspaces, setWorkspaces] = useState<Workspace[]>([])
  const [selectedRepos, setSelectedRepos] = useState<{ slug: string; base_branch: string }[]>([])
  const [models, setModels] = useState<AiModel[]>([])
  const [selectedModelId, setSelectedModelId] = useState<string>('')
  const [convUsage, setConvUsage] = useState<ConversationUsage>({
    total_prompt_tokens: 0,
    total_completion_tokens: 0,
    total_cost_usd: 0,
  })
  const [liveUsage, setLiveUsage] = useState<DoneEvent | null>(null)

  const sortedModels = useMemo(() => sortModelsForSelect(models), [models])

  const [thoughtSteps, setThoughtSteps] = useState<ThoughtStep[]>([])
  const [streamStartedAt, setStreamStartedAt] = useState<number | null>(null)
  const [streamElapsedMs, setStreamElapsedMs] = useState(0)
  const [pendingAction, setPendingAction] = useState<ActionRequiredEvent | null>(null)
  const [sessionProgress, setSessionProgress] = useState<SessionStageState[]>([])
  const [sessionProgressAnchor, setSessionProgressAnchor] = useState<SessionProgressAnchor | null>(null)

  // Anexos pendentes de envio (uploads em curso, concluídos ou falhados).
  // Apenas itens `kind === 'uploaded'` viajam no payload do streamAssistantReply.
  const [trayItems, setTrayItems] = useState<TrayItem[]>([])
  const [isDragOver, setIsDragOver] = useState(false)
  const fileInputRef = useRef<HTMLInputElement | null>(null)

  /**
   * Faz upload de uma lista de imagens, registando placeholders na tray
   * enquanto a Promise resolve. Anexos exigem `activeId` — antes de criar
   * a conversa o input file fica desativado.
   */
  const uploadFiles = useCallback(
    (files: File[]) => {
      if (!activeId || files.length === 0) return
      for (const file of files) {
        if (!ALLOWED_ATTACHMENT_MIME.has(file.type)) {
          setTrayItems((prev) => [
            ...prev,
            {
              kind: 'failed',
              localId: crypto.randomUUID(),
              filename: file.name,
              error: 'Tipo não suportado (use PNG, JPG, WebP ou GIF)',
            },
          ])
          continue
        }
        if (file.size > MAX_ATTACHMENT_BYTES) {
          setTrayItems((prev) => [
            ...prev,
            {
              kind: 'failed',
              localId: crypto.randomUUID(),
              filename: file.name,
              error: `Acima de ${(MAX_ATTACHMENT_BYTES / 1024 / 1024).toFixed(0)} MB`,
            },
          ])
          continue
        }
        const localId = crypto.randomUUID()
        const ctrl = new AbortController()
        setTrayItems((prev) => [
          ...prev,
          {
            kind: 'uploading',
            localId,
            filename: file.name,
            abort: () => ctrl.abort(),
          },
        ])
        uploadAttachment(token, activeId, file, ctrl.signal)
          .then((att) => {
            setTrayItems((prev) =>
              prev.map((it) =>
                it.localId === localId
                  ? { kind: 'uploaded', localId, attachment: att }
                  : it,
              ),
            )
          })
          .catch((e) => {
            if (e instanceof Error && e.name === 'AbortError') {
              setTrayItems((prev) => prev.filter((it) => it.localId !== localId))
              return
            }
            setTrayItems((prev) =>
              prev.map((it) =>
                it.localId === localId
                  ? {
                      kind: 'failed',
                      localId,
                      filename: file.name,
                      error: e instanceof Error ? e.message : String(e),
                    }
                  : it,
              ),
            )
          })
      }
    },
    [activeId, token],
  )

  /** Remove um item da tray; aborta uploads em curso e apaga uploads concluídos no backend. */
  const removeTrayItem = useCallback(
    (localId: string) => {
      const item = trayItems.find((it) => it.localId === localId)
      if (!item) return
      if (item.kind === 'uploading') item.abort()
      if (item.kind === 'uploaded' && activeId) {
        deleteAttachment(token, activeId, item.attachment.id).catch(() => {
          // melhor-esforço; o registo expira com a conversa via FK CASCADE
        })
      }
      setTrayItems((prev) => prev.filter((it) => it.localId !== localId))
    },
    [trayItems, activeId, token],
  )

  /** Limpa a tray sem chamar DELETE — usado após envio bem-sucedido (anexos
   *  ficam vinculados à conversa e sobrevivem como histórico no banco). */
  const clearTrayLocal = useCallback(() => setTrayItems([]), [])

  /** Handler para input file e drag&drop. */
  const handleFileSelection = useCallback(
    (fileList: FileList | null | undefined) => {
      if (!fileList || fileList.length === 0) return
      const files = Array.from(fileList)
      uploadFiles(files)
    },
    [uploadFiles],
  )

  /** Handler para colar imagem do clipboard (Ctrl+V no textarea). */
  const handlePaste = useCallback(
    (e: React.ClipboardEvent<HTMLTextAreaElement>) => {
      const items = e.clipboardData?.items
      if (!items) return
      const images: File[] = []
      for (let i = 0; i < items.length; i++) {
        const it = items[i]
        if (it.kind === 'file' && it.type.startsWith('image/')) {
          const f = it.getAsFile()
          if (f) images.push(f)
        }
      }
      if (images.length > 0) {
        e.preventDefault()
        uploadFiles(images)
      }
    },
    [uploadFiles],
  )

  const [sidePanel, setSidePanel] = useState<'none' | 'diff' | 'files'>('none')
  const [diff, setDiff] = useState<ConversationDiff | null>(null)
  const [diffLoading, setDiffLoading] = useState(false)

  const [diffStats, setDiffStats] = useState<{ added: number; removed: number } | null>(null)
  const [prLoading, setPrLoading] = useState(false)
  const [prUrl, setPrUrl] = useState<string | null>(null)
  const [prError, setPrError] = useState<string | null>(null)
  const [headBranch, setHeadBranch] = useState<string | null>(null)

  const { pathname } = useLocation()

  const abortControllerRef = useRef<AbortController | null>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  /** Comprimento do `accumulated` text já aplicado à timeline thoughtSteps. */
  const lastTextOffsetRef = useRef(0)

  // Tick do contador de tempo decorrido enquanto o stream está activo.
  useEffect(() => {
    if (streamStartedAt === null) return
    const id = window.setInterval(() => {
      setStreamElapsedMs(Date.now() - streamStartedAt)
    }, 200)
    return () => window.clearInterval(id)
  }, [streamStartedAt])

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === 'n') {
        e.preventDefault()
        handleNewChat()
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [])

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const [convsResult, wsList, modelsList] = await Promise.allSettled([
          fetchConversations(token),
          fetchWorkspaces(token),
          fetchAiModels(token),
        ])
        if (modelsList.status === 'fulfilled') {
          const ms = modelsList.value
          setModels(ms)
          // Auto-seleciona o modelo default de texto, se existir
          const defaultModel = ms.find((m) => m.is_default?.text)
          if (defaultModel) setSelectedModelId(defaultModel.model_id)
        }
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
    if (!activeId) {
      setMessages([])
      setMessagesLoading(false)
      setMessagesError(null)
      setConvUsage({ total_prompt_tokens: 0, total_completion_tokens: 0, total_cost_usd: 0 })
      setLiveUsage(null)
      return
    }
    let cancelled = false
    setDiffStats(null)
    setDiff(null)
    setPrUrl(null)
    setHeadBranch(null)
    setMessages([])
    setMessagesLoading(true)
    setMessagesError(null)
    setLiveUsage(null)
    ;(async () => {
      try {
        const [msgs, usage] = await Promise.all([
          fetchMessages(token, activeId),
          fetchConversationUsage(token, activeId),
        ])
        if (!cancelled) {
          setMessages(msgs)
          setConvUsage(usage)
        }
      } catch (e) {
        if (e instanceof AuthError) {
          setToken(null)
          window.location.href = '/login'
          return
        }
        if (!cancelled) setMessagesError(errorToUserMessage(e))
      } finally {
        if (!cancelled) setMessagesLoading(false)
      }
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
    setPrError(null)
    try {
      const result = await createConversationPr(token, activeId)
      setPrUrl(result.pr_url)
      setHeadBranch(result.head_branch)
    } catch (e) {
      setPrError(e instanceof Error ? e.message : 'Não foi possível criar o PR. Tente novamente.')
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
    setMessagesError(null)
    setMessagesLoading(false)
    setSessionProgressAnchor(null)
    setTimeout(() => inputRef.current?.focus(), 50)
  }

  /** Seleciona uma conversa histórica sem deixar o streaming atual contaminar a UI. */
  function handleSelectConversation(conversationId: string) {
    if (conversationId === activeId) return
    abortControllerRef.current?.abort()
    abortControllerRef.current = null
    setStreaming(false)
    setThoughtSteps([])
    setPendingAction(null)
    setSessionProgress([])
    setSessionProgressAnchor(null)
    setInput('')
    setSidePanel('none')
    setActiveId(conversationId)
    closeMobile()
  }

  /** Cria conversa e envia a mensagem inicial de uma vez */
  async function handleNewChatWithMessage(text: string) {
    if (!text.trim()) return
    const repos = selectedRepos.map(r => ({ slug: r.slug, base_branch: r.base_branch || null }))
    const c = await createConversation(token, repos)
    // Update otimista do título — o backend renomeia "Nova conversa" para o
    // início da primeira mensagem (mesma lógica de _TITLE_MAX_LEN=80).
    const previewTitle =
      text.length > 80 ? text.slice(0, 80) + '…' : text
    const cWithTitle = { ...c, title: previewTitle }
    setConversations((prev) => [cWithTitle, ...prev])
    setActiveId(c.id)
    setMessages([])
    setInput('')

    setStreaming(true)
    setThoughtSteps([])
    lastTextOffsetRef.current = 0
    setStreamStartedAt(Date.now())
    setStreamElapsedMs(0)
    setPendingAction(null)
    setSessionProgress([])

    const ctrl = new AbortController()
    abortControllerRef.current = ctrl

    const userMsg: ChatMessage = {
      id: randomId(),
      role: 'user',
      content: text,
      created_at: new Date().toISOString(),
    }
    setSessionProgressAnchor({ id: userMsg.id, content: userMsg.content })
    setMessages([userMsg])

    try {
      await streamAssistantReply(token, c.id, text, {
        onText(accumulated) {
          const delta = accumulated.slice(lastTextOffsetRef.current)
          lastTextOffsetRef.current = accumulated.length
          if (delta) {
            setThoughtSteps((prev) => appendTextToThoughts(prev, delta))
          }
        },
        onToolStart(tool) {
          setThoughtSteps((prev) => appendToolStartToThoughts(prev, tool))
        },
        onToolResult(result) {
          setThoughtSteps((prev) => applyToolResultToThoughts(prev, result))
        },
        onActionRequired(action) { setPendingAction(action) },
        onStatus(status) {
          const statusWithMode = { ...status, mode: status.mode ?? 'initializing' }
          setSessionProgress((prev) =>
            reduceSessionProgress(
              prev.length ? prev : createSessionProgress(statusWithMode.mode),
              statusWithMode,
            )
          )
        },
        onError(message) {
          setMessages((m) => [
            ...m,
            {
              id: randomId(),
              role: 'assistant',
              content: `**Erro:** ${message}`,
              created_at: new Date().toISOString(),
            },
          ])
        },
        onDone(usage) { setLiveUsage(usage) },
        signal: ctrl.signal,
      }, selectedModelId || null)
      setThoughtSteps([])
      setStreamStartedAt(null)
      clearTrayLocal()
      const [msgs, totals] = await Promise.all([
        fetchMessages(token, c.id),
        fetchConversationUsage(token, c.id),
      ])
      setMessages(msgs)
      setConvUsage(totals)
      setLiveUsage(null)
    } catch (e) {
      if (e instanceof AuthError) {
        setToken(null); window.location.href = '/login'; return
      } else if (e instanceof Error && e.name === 'AbortError') {
        // Cancelled by user — silently finalize
      } else {
        setMessages((m) => [
          ...m,
          {
            id: randomId(),
            role: 'assistant',
            content: `**Erro:** ${e instanceof Error ? e.message : String(e)}`,
            created_at: new Date().toISOString(),
          },
        ])
      }
    } finally {
      setStreaming(false)
      setStreamStartedAt(null)
      abortControllerRef.current = null
      fetchConversationDiff(token, c.id).then((d) => setDiffStats(d.stats)).catch(() => {})
    }
  }

  async function handleSend(textOverride?: string) {
    const text = (textOverride ?? input).trim()
    if (!text || !activeId || streaming) return

    // Bloqueia envio enquanto houver uploads em curso para não perder o
    // anexo no meio do streaming. Failed items podem ficar — o utilizador
    // já viu o erro e decide se remove ou tenta de novo.
    if (trayItems.some((it) => it.kind === 'uploading')) return
    const uploadedAttachmentIds = trayItems
      .filter((it): it is Extract<TrayItem, { kind: 'uploaded' }> => it.kind === 'uploaded')
      .map((it) => it.attachment.id)

    const sessionMode: SessionMode = 'resuming'

    if (!textOverride) setInput('')
    setStreaming(true)
    setThoughtSteps([])
    lastTextOffsetRef.current = 0
    setStreamStartedAt(Date.now())
    setStreamElapsedMs(0)
    setPendingAction(null)
    setSessionProgress([])

    const ctrl = new AbortController()
    abortControllerRef.current = ctrl

    const userMsg: ChatMessage = {
      id: randomId(),
      role: 'user',
      content: text,
      created_at: new Date().toISOString(),
    }
    setSessionProgressAnchor({ id: userMsg.id, content: userMsg.content })
    setMessages((m) => [...m, userMsg])

    // Renomeia título se ainda for o default — bate com o backend.
    setConversations((prev) =>
      prev.map((c) => {
        if (c.id !== activeId) return c
        if (c.title && c.title !== 'Nova conversa') return c
        const previewTitle = text.length > 80 ? text.slice(0, 80) + '…' : text
        return { ...c, title: previewTitle }
      }),
    )

    try {
      await streamAssistantReply(token, activeId, text, {
        onText(accumulated) {
          const delta = accumulated.slice(lastTextOffsetRef.current)
          lastTextOffsetRef.current = accumulated.length
          if (delta) {
            setThoughtSteps((prev) => appendTextToThoughts(prev, delta))
          }
        },
        onToolStart(tool) {
          setThoughtSteps((prev) => appendToolStartToThoughts(prev, tool))
        },
        onToolResult(result) {
          setThoughtSteps((prev) => applyToolResultToThoughts(prev, result))
        },
        onActionRequired(action) { setPendingAction(action) },
        onStatus(status) {
          const statusWithMode = { ...status, mode: sessionMode }
          setSessionProgress((prev) =>
            reduceSessionProgress(
              prev.length ? prev : createSessionProgress(statusWithMode.mode),
              statusWithMode,
            )
          )
        },
        onError(message) {
          setMessages((m) => [
            ...m,
            {
              id: randomId(),
              role: 'assistant',
              content: `**Erro:** ${message}`,
              created_at: new Date().toISOString(),
            },
          ])
        },
        onDone(usage) { setLiveUsage(usage) },
        signal: ctrl.signal,
      }, selectedModelId || null, uploadedAttachmentIds.length ? uploadedAttachmentIds : null)
      setThoughtSteps([])
      setStreamStartedAt(null)
      clearTrayLocal()
      const [msgs, totals] = await Promise.all([
        fetchMessages(token, activeId),
        fetchConversationUsage(token, activeId),
      ])
      setMessages(msgs)
      setConvUsage(totals)
      setLiveUsage(null)
    } catch (e) {
      if (e instanceof AuthError) {
        setToken(null); window.location.href = '/login'; return
      } else if (e instanceof Error && e.name === 'AbortError') {
        // Cancelled by user — silently finalize
      } else {
        setMessages((m) => [
          ...m,
          {
            id: randomId(),
            role: 'assistant',
            content: `**Erro:** ${e instanceof Error ? e.message : String(e)}`,
            created_at: new Date().toISOString(),
          },
        ])
      }
    } finally {
      setStreaming(false)
      setStreamStartedAt(null)
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
  const showThinking =
    streaming &&
    !sessionProgress.length &&
    thoughtSteps.length === 0 &&
    !pendingAction

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

          <nav className={styles.sidebarNav} aria-label="Áreas do produto">
            {[
              { to: '/', icon: 'dashboard', label: 'Dashboard' },
              { to: '/chat', icon: 'chat_bubble', label: 'Chat' },
              { to: '/runs', icon: 'history', label: 'Runs' },
              { to: '/analytics', icon: 'analytics', label: 'Analytics' },
              { to: '/skills', icon: 'menu_book', label: 'Skills' },
              { to: '/mcp', icon: 'extension', label: 'MCP' },
              { to: '/settings', icon: 'settings', label: 'Configurações' },
            ].map(({ to, icon, label }) => {
              const isActive = pathname === to
              return (
                <Link
                  key={to}
                  to={to}
                  className={`${styles.sidebarNavItem} ${isActive ? styles.sidebarNavItemActive : ''}`}
                  aria-current={isActive ? 'page' : undefined}
                  title={label}
                >
                  <span className={styles.icon}>{icon}</span>
                  <span>{label}</span>
                </Link>
              )
            })}
          </nav>

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
                      onClick={() => handleSelectConversation(c.id)}
                    >
                      <span className={`${styles.icon} ${styles.sessionIcon}`}>
                        chat_bubble
                      </span>
                      <span className={styles.sessionLabel}>{c.title}</span>
                      {c.repos?.[0]?.slug && (
                        <span className={styles.sessionEnvDot} title={c.repos[0].slug} />
                      )}
                    </button>
                  ))}
                </div>
              </section>
            ))}
          </div>

          <div className={styles.sidebarFooter}>
            <button type="button" className={styles.sidebarLogoutBtn} onClick={logout} title="Sair">
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
            selectedRepos={selectedRepos}
            setSelectedRepos={setSelectedRepos}
            models={sortedModels}
            selectedModelId={selectedModelId}
            setSelectedModelId={setSelectedModelId}
            token={token}
          />
          ) : (
            <ActiveChat
              messages={messages}
              messagesLoading={messagesLoading}
              messagesError={messagesError}
              sessionProgressAnchor={sessionProgressAnchor}
              thoughtSteps={thoughtSteps}
              streamElapsedMs={streamElapsedMs}
              sessionProgress={sessionProgress}
              pendingAction={pendingAction}
              showThinking={showThinking}
              streaming={streaming}
              input={input}
              setInput={setInput}
              inputRef={inputRef}
              onSend={() => handleSend()}
              onStop={handleStop}
              onActionReply={handleActionReply}
              activeRepos={activeConv?.repos ?? []}
              workspaces={workspaces}
              diffStats={diffStats}
              prLoading={prLoading}
              prUrl={prUrl}
              prError={prError}
              headBranch={headBranch}
              onCreatePr={handleCreatePr}
              activeTitle={activeConv?.title ?? 'Conversa'}
              token={token}
              conversationId={activeId!}
              conversations={conversations}
              setConversations={setConversations}
              sidePanel={sidePanel}
              diff={diff}
              diffLoading={diffLoading}
              onOpenDiff={handleOpenDiff}
              onToggleFiles={handleToggleFiles}
              models={sortedModels}
              selectedModelId={selectedModelId}
              setSelectedModelId={setSelectedModelId}
              convUsage={convUsage}
              liveUsage={liveUsage}
              trayItems={trayItems}
              onPickFiles={handleFileSelection}
              onPasteFiles={handlePaste}
              onRemoveTrayItem={removeTrayItem}
              fileInputRef={fileInputRef}
              isDragOver={isDragOver}
              setDragOver={setIsDragOver}
            />
          )}
        </main>
      </div>
    </div>
  )
}

/* ────────────────────────────────────────────────────────────────
   Empty State — command bar premium centralizada (multi-repo)
   ──────────────────────────────────────────────────────────────── */
interface EmptyStateProps {
  input: string
  setInput: (v: string) => void
  inputRef: React.RefObject<HTMLTextAreaElement | null>
  onExecute: (text: string) => void
  streaming: boolean
  workspaces: Workspace[]
  selectedRepos: { slug: string; base_branch: string }[]
  setSelectedRepos: Dispatch<SetStateAction<{ slug: string; base_branch: string }[]>>
  models: AiModel[]
  selectedModelId: string
  setSelectedModelId: (id: string) => void
  token: string
}

/** Per-repo branch cache keyed by slug */
type BranchCache = Record<string, { branches: string[]; default: string; loading: boolean }>

function EmptyState({
  input, setInput, inputRef, onExecute, streaming,
  workspaces, selectedRepos, setSelectedRepos,
  models, selectedModelId, setSelectedModelId, token,
}: EmptyStateProps) {
  const [branchCache, setBranchCache] = useState<BranchCache>({})

  const canExecute = selectedRepos.length > 0 && selectedRepos.every(r => !!r.base_branch) && !!input.trim() && !streaming

  // Fetch branches when a repo is added
  useEffect(() => {
    for (const repo of selectedRepos) {
      if (branchCache[repo.slug] && !branchCache[repo.slug].loading) continue
      if (branchCache[repo.slug]?.loading) continue
      setBranchCache(prev => ({ ...prev, [repo.slug]: { branches: [], default: 'main', loading: true } }))
      fetchBranches(token, repo.slug).then(({ branches: list, default: def }) => {
        setBranchCache(prev => ({ ...prev, [repo.slug]: { branches: list, default: def, loading: false } }))
        // Auto-set branch if not yet set
        setSelectedRepos(prev => prev.map(r =>
          r.slug === repo.slug && !r.base_branch ? { ...r, base_branch: def } : r
        ))
      })
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedRepos.map(r => r.slug).join(','), token])

  function handleAddRepo(slug: string) {
    if (!slug || selectedRepos.some(r => r.slug === slug)) return
    setSelectedRepos(prev => [...prev, { slug, base_branch: '' }])
  }

  function handleRemoveRepo(slug: string) {
    setSelectedRepos(prev => prev.filter(r => r.slug !== slug))
  }

  function handleBranchChange(slug: string, branch: string) {
    setSelectedRepos(prev => prev.map(r => r.slug === slug ? { ...r, base_branch: branch } : r))
  }

  function handleKey(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey && !streaming) {
      e.preventDefault()
      if (canExecute) onExecute(input)
    }
  }

  const availableWorkspaces = workspaces.filter(w => !selectedRepos.some(r => r.slug === w.slug))
  const repoRequired = workspaces.length > 0 && selectedRepos.length === 0
  const selectedModelName =
    models.find((model) => model.model_id === selectedModelId)?.display_name ?? 'Modelo padrão'

  return (
    <div className={styles.emptyState}>
      <section className={styles.welcomePanel}>
        <div className={styles.mascotWrapper}>
          <img src="/capybara.png" alt="CappyCloud" className={styles.mascot} />
          <div className={styles.mascotGlow} />
        </div>
        <div className={styles.welcomeCopy}>
          <span className={styles.welcomeEyebrow}>CappyCloud Command Center</span>
          <h1 className={styles.welcomeTitle}>Desenvolva com OpenClaude em worktrees isolados.</h1>
          <p className={styles.welcomeText}>
            Escolha os repositórios, descreva a tarefa e acompanhe execução, ferramentas,
            diff e PR a partir de uma única superfície.
          </p>
        </div>
        <div className={styles.welcomeMetrics} aria-label="Resumo da sessão">
          <div className={styles.metricCard}>
            <span className={styles.metricValue}>{workspaces.length}</span>
            <span className={styles.metricLabel}>repositórios</span>
          </div>
          <div className={styles.metricCard}>
            <span className={styles.metricValue}>{models.length || 1}</span>
            <span className={styles.metricLabel}>modelos</span>
          </div>
        </div>
      </section>

      {/* Selected repos list */}
      {selectedRepos.length > 0 && (
        <div className={styles.selectedReposList}>
          {selectedRepos.map((repo) => {
            const cache = branchCache[repo.slug]
            const ws = workspaces.find(w => w.slug === repo.slug)
            return (
              <div key={repo.slug} className={styles.selectedRepoItem}>
                <span className={styles.icon} style={{ fontSize: '0.9rem', opacity: 0.6 }}>source</span>
                <span className={styles.selectedRepoName}>{ws?.name ?? repo.slug}</span>
                <div className={`${styles.contextPill} ${!repo.base_branch ? styles.contextPillRequired : ''}`} style={{ marginLeft: '0.5rem' }}>
                  <span className={styles.icon} style={{ fontSize: '0.875rem', opacity: 0.6 }}>fork_right</span>
                  <span className={styles.contextPillLabel} style={!repo.base_branch ? { opacity: 0.45 } : undefined}>
                    {cache?.loading ? '…' : (repo.base_branch || 'Branch…')}
                  </span>
                  <span className={styles.icon} style={{ fontSize: '0.75rem', opacity: 0.35 }}>expand_more</span>
                  <select
                    className={styles.contextPillSelect}
                    value={repo.base_branch}
                    onChange={(e) => handleBranchChange(repo.slug, e.target.value)}
                    disabled={cache?.loading}
                    title="Selecionar branch"
                  >
                    {!repo.base_branch && !cache?.loading && (
                      <option value="" disabled>Selecionar branch…</option>
                    )}
                    {(cache?.branches ?? []).map((b) => (
                      <option key={b} value={b}>{b}</option>
                    ))}
                  </select>
                </div>
                <button
                  type="button"
                  className={styles.selectedRepoRemove}
                  onClick={() => handleRemoveRepo(repo.slug)}
                  title="Remover repositório"
                >
                  <span className={styles.icon} style={{ fontSize: '0.85rem' }}>close</span>
                </button>
              </div>
            )
          })}
        </div>
      )}

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
                  selectedRepos.length === 0
                    ? 'Selecione ao menos um repositório para continuar…'
                    : selectedRepos.some(r => !r.base_branch)
                      ? 'Selecione a branch de cada repositório…'
                      : 'Descreva o que o agente deve fazer…'
                }
                rows={2}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKey}
                disabled={selectedRepos.length === 0 || selectedRepos.some(r => !r.base_branch)}
              />
            </div>

            <div className={styles.commandToolbar}>
              <div className={styles.commandToolbarLeft}>
                <button className={styles.toolbarBtn} title="Anexar" disabled={selectedRepos.length === 0}>
                  <span className={styles.icon}>attachment</span>
                </button>
                {workspaces.length > 0 ? (
                  <div
                    className={`${styles.contextPill} ${repoRequired ? styles.contextPillRequired : ''}`}
                    style={{ marginLeft: '0.5rem' }}
                  >
                    <span className={styles.icon} style={{ fontSize: '0.875rem', opacity: 0.6 }}>
                      add_circle
                    </span>
                    <span className={styles.contextPillLabel} style={selectedRepos.length === 0 ? { opacity: 0.45 } : undefined}>
                      {selectedRepos.length === 0 ? 'Adicionar repo…' : `${selectedRepos.length} repo(s)`}
                    </span>
                    <span className={styles.icon} style={{ fontSize: '0.75rem', opacity: 0.35 }}>
                      expand_more
                    </span>
                    <select
                      className={styles.contextPillSelect}
                      value=""
                      onChange={(e) => handleAddRepo(e.target.value)}
                      title="Adicionar repositório"
                    >
                      <option value="" disabled>Adicionar repositório…</option>
                      {availableWorkspaces.map((w) => (
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
                {models.length > 0 && (
                  <div style={{ marginLeft: '0.25rem' }}>
                    <ModelPicker
                      models={models}
                      value={selectedModelId}
                      onChange={setSelectedModelId}
                    />
                  </div>
                )}
              </div>

              <div className={styles.commandToolbarRight}>
                <button
                  className={styles.executeBtn}
                  onClick={() => canExecute && onExecute(input)}
                  disabled={!canExecute}
                  title={
                    selectedRepos.length === 0 ? 'Selecione ao menos um repositório' :
                    selectedRepos.some(r => !r.base_branch) ? 'Selecione a branch de cada repositório' :
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
          icon="source"
          iconColor="var(--cc-secondary)"
          title={selectedRepos.length > 0 ? `${selectedRepos.length} repositório(s)` : 'Nenhum selecionado'}
          desc="Sessões isoladas por worktree, prontas para diff e PR."
          href="/settings"
        />
        <QuickActionCard
          icon="smart_toy"
          iconColor="var(--cc-error)"
          title={selectedModelName}
          desc="Modelo selecionado para novas execuções do agente."
        />
      </div>
    </div>
  )
}

/** Renderiza um atalho contextual da tela inicial do agente. */
function QuickActionCard({ icon, iconColor, title, desc, href }: {
  icon: string; iconColor: string; title: string; desc: string; href?: string
}) {
  const content = (
    <div className={styles.quickCard}>
      <div className={styles.quickCardHeader}>
        <span className={styles.icon} style={{ color: iconColor }}>{icon}</span>
        <span className={styles.quickCardTitle}>{title}</span>
      </div>
      <p className={styles.quickCardDesc}>{desc}</p>
    </div>
  )

  if (!href) return content

  return (
    <Link to={href} className={styles.quickCardLink}>
      {content}
    </Link>
  )
}

/* ────────────────────────────────────────────────────────────────
   Active Chat — mensagens + input compacto
   ──────────────────────────────────────────────────────────────── */
interface ActiveChatProps {
  messages: ChatMessage[]
  messagesLoading: boolean
  messagesError: string | null
  sessionProgressAnchor: SessionProgressAnchor | null
  thoughtSteps: ThoughtStep[]
  streamElapsedMs: number
  sessionProgress: SessionStageState[]
  pendingAction: ActionRequiredEvent | null
  showThinking: boolean
  streaming: boolean
  input: string
  setInput: (v: string) => void
  inputRef: React.RefObject<HTMLTextAreaElement | null>
  onSend: () => void
  onStop: () => void
  onActionReply: (r: string) => void
  activeRepos: Array<Record<string, unknown>>
  workspaces: Workspace[]
  diffStats: { added: number; removed: number } | null
  prLoading: boolean
  prUrl: string | null
  prError: string | null
  headBranch: string | null
  onCreatePr: () => void
  activeTitle: string
  token: string
  conversationId: string
  conversations: Conversation[]
  setConversations: Dispatch<SetStateAction<Conversation[]>>
  sidePanel: 'none' | 'diff' | 'files'
  diff: ConversationDiff | null
  diffLoading: boolean
  onOpenDiff: () => void
  onToggleFiles: () => void
  models: AiModel[]
  selectedModelId: string
  setSelectedModelId: (id: string) => void
  convUsage: ConversationUsage
  liveUsage: DoneEvent | null
  // Anexos
  trayItems: TrayItem[]
  onPickFiles: (files: FileList | null | undefined) => void
  onPasteFiles: (e: React.ClipboardEvent<HTMLTextAreaElement>) => void
  onRemoveTrayItem: (localId: string) => void
  fileInputRef: React.RefObject<HTMLInputElement | null>
  isDragOver: boolean
  setDragOver: (v: boolean) => void
}

function ActiveChat({
  messages, messagesLoading, messagesError, sessionProgressAnchor, thoughtSteps, streamElapsedMs, sessionProgress, pendingAction,
  showThinking, streaming, input, setInput, inputRef,
  onSend, onStop, onActionReply, activeRepos,
  workspaces,
  diffStats, prLoading, prUrl, prError, headBranch: _headBranch, onCreatePr,
  activeTitle: _activeTitle,
  token, conversationId, conversations: _conversations, setConversations: _setConversations, sidePanel, diff, diffLoading, onOpenDiff, onToggleFiles,
  models, selectedModelId, setSelectedModelId,
  convUsage, liveUsage,
  trayItems, onPickFiles, onPasteFiles, onRemoveTrayItem, fileInputRef, isDragOver, setDragOver,
}: ActiveChatProps) {
  const scrollRef = useRef<HTMLDivElement>(null)
  const shouldStickToBottomRef = useRef(true)
  const [elapsedSecs, setElapsedSecs] = useState(0)
  const [showJumpToLatest, setShowJumpToLatest] = useState(false)

  /** Mantém o auto-scroll apenas quando o usuário já está no fim da conversa. */
  const updateStickyScroll = useCallback(() => {
    const viewport = scrollRef.current
    if (!viewport) return true
    const distanceFromBottom = viewport.scrollHeight - viewport.scrollTop - viewport.clientHeight
    const isNearBottom = distanceFromBottom <= STICKY_SCROLL_THRESHOLD_PX
    shouldStickToBottomRef.current = isNearBottom
    if (isNearBottom) setShowJumpToLatest(false)
    return isNearBottom
  }, [])

  /** Volta para as mensagens novas e reativa o acompanhamento do streaming. */
  const scrollToLatest = useCallback((behavior: ScrollBehavior = 'auto') => {
    const viewport = scrollRef.current
    if (!viewport) return
    shouldStickToBottomRef.current = true
    setShowJumpToLatest(false)
    viewport.scrollTo({ top: viewport.scrollHeight, behavior })
  }, [])

  useEffect(() => {
    if (!streaming) return
    const id = setInterval(() => setElapsedSecs((s) => s + 1), 1000)
    return () => {
      clearInterval(id)
      setElapsedSecs(0)
    }
  }, [streaming])

  useEffect(() => {
    shouldStickToBottomRef.current = true
    requestAnimationFrame(() => scrollToLatest())
  }, [conversationId, scrollToLatest])

  useEffect(() => {
    if (shouldStickToBottomRef.current) {
      requestAnimationFrame(() => scrollToLatest())
    } else {
      requestAnimationFrame(() => setShowJumpToLatest(true))
    }
  }, [messages, thoughtSteps, sessionProgress, pendingAction, streaming, scrollToLatest])

  let sessionProgressAfterIndex = -1
  if (sessionProgressAnchor) {
    for (let index = messages.length - 1; index >= 0; index -= 1) {
      const message = messages[index]
      if (
        message.id === sessionProgressAnchor.id ||
        (message.role === 'user' && message.content === sessionProgressAnchor.content)
      ) {
        sessionProgressAfterIndex = index
        break
      }
    }
    if (sessionProgressAfterIndex < 0) {
      for (let index = messages.length - 1; index >= 0; index -= 1) {
        if (messages[index].role === 'user') {
          sessionProgressAfterIndex = index
          break
        }
      }
    }
  }

  return (
    <div className={styles.activeChat}>
      {/* Session header — env + branch + diff stats + PR + painel ficheiros/diff */}
      <div className={styles.sessionHeader}>
        <div className={styles.sessionHeaderInner}>
          <div className={styles.sessionHeaderLeft}>
          {activeRepos.length > 0 ? (
            <>
              {activeRepos.map((repo, idx) => {
                const slug = String(repo.slug ?? '')
                const alias = String(repo.alias ?? slug)
                const branch = String(repo.base_branch ?? '')
                const ws = workspaces.find(w => w.slug === slug)
                return (
                  <span key={alias} style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem' }}>
                    {idx > 0 && <span style={{ opacity: 0.3, margin: '0 0.35rem' }}>·</span>}
                    <span className={`${styles.icon} ${styles.sessionHeaderIcon}`}>source</span>
                    <span className={styles.sessionHeaderEnv}>{ws?.name ?? alias}</span>
                    {branch && (
                      <>
                        <span className={styles.sessionHeaderArrow}>›</span>
                        <span className={styles.sessionHeaderBranch}>{branch}</span>
                      </>
                    )}
                  </span>
                )
              })}
            </>
          ) : (
            <span className={styles.sessionHeaderEnv} style={{ opacity: 0.85 }}>
              Conversa (sem repositório ligado)
            </span>
          )}
          </div>
          <div className={styles.sessionHeaderRight}>
          {diffStats && (diffStats.added > 0 || diffStats.removed > 0) && (
            <>
              <span className={styles.diffAdded}>+{diffStats.added}</span>
              <span className={styles.diffRemoved}>-{diffStats.removed}</span>
              {activeRepos.length > 0 && (
                prUrl ? (
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
                  <>
                    <button
                      type="button"
                      className={styles.createPrBtn}
                      onClick={onCreatePr}
                      disabled={prLoading || streaming}
                    >
                      {prLoading ? 'Criando…' : 'Criar PR'}
                    </button>
                    {prError && (
                      <span
                        role="alert"
                        style={{ fontSize: '0.72rem', color: 'var(--mantine-color-red-5)', maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                        title={prError}
                      >
                        {prError}
                      </span>
                    )}
                  </>
                )
              )}
            </>
          )}
          <div className={styles.sessionHeaderPanelBtns}>
            <button
              type="button"
              className={`${styles.chatContextIconBtn} ${sidePanel === 'files' ? styles.chatContextIconBtnActive : ''}`}
              onClick={onToggleFiles}
              title="Explorador de ficheiros"
            >
              <span className={styles.icon}>folder_open</span>
            </button>
            <button
              type="button"
              className={`${styles.chatContextIconBtn} ${sidePanel === 'diff' ? styles.chatContextIconBtnActive : ''}`}
              onClick={onOpenDiff}
              title="Ver diff"
            >
              <span className={styles.icon}>difference</span>
            </button>
          </div>
          </div>
        </div>
      </div>
      <div className={styles.chatBody}>
        {/* Messages column */}
        <div className={styles.chatMessages}>
          <ScrollArea
            className={styles.messageArea}
            viewportRef={scrollRef}
            type="auto"
            onScrollPositionChange={updateStickyScroll}
          >
            <div className={styles.chatScrollInner}>
              <div className={styles.chatThread}>
              <Stack gap="sm" p="md">
              {messagesLoading && (
                <div className={styles.chatStateCard}>
                  <ThinkingIndicator label="A carregar conversa…" />
                </div>
              )}
              {messagesError && (
                <div className={`${styles.chatStateCard} ${styles.chatStateCardError}`} role="alert">
                  <Text size="sm" fw={600}>Não foi possível carregar esta conversa.</Text>
                  <Text size="xs" c="dimmed">{messagesError}</Text>
                </div>
              )}
              {!messagesLoading && !messagesError && messages.length === 0 && (
                <div className={styles.chatStateCard}>
                  <Text size="sm" c="dimmed">Esta conversa ainda não tem mensagens.</Text>
                </div>
              )}
              {sessionProgress.length > 0 && sessionProgressAfterIndex < 0 && (
                <SessionProgressCard stages={sessionProgress} />
              )}
              {messages.map((m, index) => (
                <Fragment key={m.id}>
                  <PaperMessage
                    key={m.id}
                    role={m.role}
                    content={m.content}
                    modelUsed={m.model_used ?? null}
                    promptTokens={m.prompt_tokens ?? 0}
                    completionTokens={m.completion_tokens ?? 0}
                    costUsd={m.cost_usd ?? 0}
                  />
                  {sessionProgress.length > 0 && index === sessionProgressAfterIndex && (
                    <SessionProgressCard stages={sessionProgress} />
                  )}
                </Fragment>
              ))}
              {(thoughtSteps.length > 0 || streaming) && (
                <Stack gap="xs">
                  {thoughtSteps.length > 0 && (
                    <ThinkingStream
                      steps={thoughtSteps}
                      streaming={streaming}
                      elapsedMs={streamElapsedMs}
                    />
                  )}
                  {streaming &&
                    sessionProgress.length === 0 &&
                    showThinking && <ThinkingIndicator />}
                </Stack>
              )}

              {pendingAction && (
                <ActionRequiredCard action={pendingAction} onReply={onActionReply} />
              )}
              </Stack>
              </div>
            </div>
          </ScrollArea>
          {showJumpToLatest && (
            <button type="button" className={styles.jumpToLatestBtn} onClick={() => scrollToLatest('smooth')}>
              <span>Novas mensagens</span>
              <span className={styles.icon}>south</span>
            </button>
          )}
        </div>

        {/* Side panel — wrapper flex evita altura 0 com ScrollArea/diff */}
        {sidePanel !== 'none' && (
          <div className={styles.sidePanel}>
            <div className={styles.sidePanelFill} key={`${conversationId}-${sidePanel}`}>
              {sidePanel === 'diff' && (
                diffLoading
                  ? <div className={styles.sidePanelLoading}><Text size="xs" c="dimmed">A carregar diff…</Text></div>
                  : diff
                    ? (
                      <DiffViewer
                        key={`${conversationId}-${diff.files.map((f) => f.path).join('|')}`}
                        diff={diff}
                      />
                      )
                    : <div className={styles.sidePanelLoading}><Text size="xs" c="dimmed">Sem diff disponível</Text></div>
              )}
              {sidePanel === 'files' && (
                <FileExplorer token={token} conversationId={conversationId} />
              )}
            </div>
          </div>
        )}
      </div>

      {/* Compact input bar */}
      <div
        className={`${styles.chatInputBar} ${isDragOver ? styles.chatInputBarDragOver : ''}`}
        onDragOver={(e) => {
          if (!e.dataTransfer?.types?.includes('Files')) return
          e.preventDefault()
          setDragOver(true)
        }}
        onDragLeave={(e) => {
          if (e.currentTarget === e.target) setDragOver(false)
        }}
        onDrop={(e) => {
          e.preventDefault()
          setDragOver(false)
          onPickFiles(e.dataTransfer?.files)
        }}
      >
        <div className={styles.chatInputBarShell}>
          <div
            className={`${styles.chatInputStatusRow} ${streaming && !pendingAction ? styles.visible : ''}`}
            aria-hidden={!streaming || !!pendingAction}
          >
            {streaming && !pendingAction && (
              <ThinkingIndicator
                label={
                  thoughtSteps.some((t) => t.kind === 'tool' && !t.done)
                    ? 'A executar…'
                    : undefined
                }
              />
            )}
          </div>
          <AttachmentTray
            items={trayItems}
            token={token}
            conversationId={conversationId}
            onRemove={onRemoveTrayItem}
          />
          <div className={styles.chatInputWrapper}>
          <input
            ref={fileInputRef}
            type="file"
            accept="image/png,image/jpeg,image/jpg,image/webp,image/gif"
            multiple
            style={{ display: 'none' }}
            onChange={(e) => {
              onPickFiles(e.target.files)
              if (e.target) e.target.value = ''
            }}
          />
          <button
            type="button"
            className={styles.attachBtn}
            onClick={() => fileInputRef.current?.click()}
            disabled={streaming}
            title="Anexar imagem (PNG, JPG, WebP, GIF — até 8MB)"
            aria-label="Anexar imagem"
          >
            <span className={styles.icon}>attachment</span>
          </button>
          <textarea
            ref={inputRef}
            className={styles.chatTextarea}
            placeholder={
              isDragOver
                ? 'Solte para anexar a imagem…'
                : 'Mensagem ao agente… (Enter para enviar, cole imagens com Ctrl+V)'
            }
            rows={2}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onPaste={onPasteFiles}
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
            disabled={
              (!input.trim() && !pendingAction) ||
              (streaming && !pendingAction) ||
              trayItems.some((it) => it.kind === 'uploading')
            }
            title={
              trayItems.some((it) => it.kind === 'uploading')
                ? 'Aguarde os anexos terminarem o envio…'
                : undefined
            }
          >
            <span className={styles.icon}>keyboard_return</span>
          </button>
          )}
          </div>

          {/* Context status bar — repos + branches */}
          <div className={styles.chatContextBar}>
          {activeRepos.length > 0 ? (
            activeRepos.map((repo) => {
              const slug = String(repo.slug ?? '')
              const alias = String(repo.alias ?? slug)
              const branch = String(repo.base_branch ?? '')
              const ws = workspaces.find(w => w.slug === slug)
              return (
                <div key={alias} className={styles.chatContextPill} style={{ marginRight: '0.35rem' }}>
                  <span className={`${styles.icon} ${styles.chatContextIcon}`}>source</span>
                  <span className={styles.chatContextText}>
                    {ws?.name ?? alias}{branch ? ` › ${branch}` : ''}
                  </span>
                </div>
              )
            })
          ) : (
            <div className={styles.chatContextPill}>
              <span className={`${styles.icon} ${styles.chatContextIcon}`}>source</span>
              <span className={styles.chatContextText}>—</span>
            </div>
          )}
          {models.length > 0 && (
            <div style={{ marginLeft: '0.35rem' }}>
              <ModelPicker
                models={models}
                value={selectedModelId}
                onChange={setSelectedModelId}
                disabled={streaming}
                compact
              />
            </div>
          )}
          {(convUsage.total_prompt_tokens > 0 || convUsage.total_completion_tokens > 0) && (
            <div
              className={styles.chatContextPill}
              style={{ marginLeft: '0.35rem' }}
              title={`Total da conversa: ${convUsage.total_prompt_tokens} in + ${convUsage.total_completion_tokens} out`}
            >
              <span className={`${styles.icon} ${styles.chatContextIcon}`}>insights</span>
              <span className={styles.chatContextText}>
                {(convUsage.total_prompt_tokens + convUsage.total_completion_tokens).toLocaleString('pt-BR')} tok
                · {formatCostUsd(convUsage.total_cost_usd)}
              </span>
            </div>
          )}
          {liveUsage && (liveUsage.prompt_tokens > 0 || liveUsage.completion_tokens > 0) && (
            <div
              className={styles.chatContextPill}
              style={{ marginLeft: '0.35rem', opacity: 0.85 }}
              title="Último turno (ainda não consolidado nos totais)"
            >
              <span className={`${styles.icon} ${styles.chatContextIcon}`}>bolt</span>
              <span className={styles.chatContextText}>
                +{liveUsage.prompt_tokens + liveUsage.completion_tokens} tok agora
              </span>
            </div>
          )}
          </div>
        </div>
      </div>
    </div>
  )
}

/** Card expansível com progresso operacional da criação da sessão. */
function SessionProgressCard({ stages }: { stages: SessionStageState[] }) {
  const [expanded, setExpanded] = useState(true)
  const completed = stages.every((stage) => stage.status === 'done')
  const resuming = stages[0]?.label.includes('reativado')
  const title = completed
    ? resuming ? 'Sessão reiniciada' : 'Sessão inicializada'
    : resuming ? 'Reiniciando sessão' : 'Inicializando sessão'

  const doneCount = stages.filter((s) => s.status === 'done').length
  const progressPct = stages.length > 0 ? (doneCount / stages.length) * 100 : 0

  return (
    <div
      className={`${styles.sessionProgressCard} ${
        completed ? styles.sessionProgressCardComplete : ''
      }`}
      style={{ ['--cc-progress' as string]: `${progressPct}%` }}
    >
      <button
        type="button"
        className={styles.sessionProgressHeader}
        onClick={() => setExpanded((value) => !value)}
      >
        <span>{title}</span>
        <span className={styles.icon}>{expanded ? 'expand_less' : 'expand_more'}</span>
      </button>

      {expanded && (
        <div className={styles.sessionProgressList}>
          {stages.map((stage, index) => (
            <div
              key={stage.key}
              className={styles.sessionProgressItem}
              style={{ ['--cc-step-delay' as string]: `${index * 90}ms` }}
            >
              <span
                className={`${styles.sessionProgressIcon} ${
                  stage.status === 'done' ? styles.sessionProgressIconDone : ''
                } ${
                  stage.status === 'active' ? styles.sessionProgressIconActive : ''
                }`}
                aria-label={
                  stage.status === 'done'
                    ? 'Verificado'
                    : stage.status === 'active'
                      ? 'Verificando'
                      : 'Pendente'
                }
              >
                {stage.status === 'done' ? '✓' : ''}
              </span>
              <div>
                <Text
                  size="sm"
                  c={stage.status === 'pending' ? 'dimmed' : undefined}
                  className={
                    stage.status === 'done'
                      ? styles.sessionProgressLabelDone
                      : undefined
                  }
                >
                  {stage.label}
                </Text>
                {stage.detail && (
                  <Text size="xs" c="dimmed">
                    {stage.detail}
                  </Text>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

/* ────────────────────────────────────────────────────────────────
   Message bubble
   ──────────────────────────────────────────────────────────────── */
function PaperMessage({
  role,
  content,
  streaming,
  modelUsed,
  promptTokens,
  completionTokens,
  costUsd,
}: {
  role: string
  content: string
  streaming?: boolean
  modelUsed?: string | null
  promptTokens?: number
  completionTokens?: number
  costUsd?: number
}) {
  const isUser = role === 'user'
  const hasUsage =
    !isUser && ((promptTokens ?? 0) > 0 || (completionTokens ?? 0) > 0 || !!modelUsed)
  const showCopy = !isUser && !streaming && content.trim().length > 0
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
          <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>{content}</ReactMarkdown>
          {streaming && <span className={styles.streamingCursor} aria-hidden />}
        </div>
      )}
      {showCopy && <CopyMessageButton content={content} />}
      {hasUsage && (
        <div className={styles.messageUsageFooter}>
          {modelUsed && <span className={styles.messageUsageModel}>{modelUsed}</span>}
          {((promptTokens ?? 0) > 0 || (completionTokens ?? 0) > 0) && (
            <span className={styles.messageUsageTokens}>
              {(promptTokens ?? 0).toLocaleString('pt-BR')} in · {(completionTokens ?? 0).toLocaleString('pt-BR')} out
            </span>
          )}
          <span className={styles.messageUsageCost}>{formatCostUsd(costUsd ?? 0)}</span>
        </div>
      )}
    </div>
  )
}

/** Botão de copiar conteúdo da resposta do agente. Feedback visual por 1.6s. */
function CopyMessageButton({ content }: { content: string }) {
  const [copied, setCopied] = useState(false)

  async function handleCopy() {
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(content)
      } else {
        const ta = document.createElement('textarea')
        ta.value = content
        ta.setAttribute('readonly', '')
        ta.style.position = 'fixed'
        ta.style.opacity = '0'
        document.body.appendChild(ta)
        ta.select()
        document.execCommand('copy')
        document.body.removeChild(ta)
      }
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1600)
    } catch {
      /* silently ignore — clipboard pode estar bloqueado */
    }
  }

  return (
    <button
      type="button"
      className={`${styles.messageCopyBtn} ${copied ? styles.messageCopyBtnCopied : ''}`}
      onClick={handleCopy}
      aria-label={copied ? 'Resposta copiada' : 'Copiar resposta do agente'}
      title={copied ? 'Copiado!' : 'Copiar'}
    >
      <span className={styles.messageCopyIcon} aria-hidden="true">
        {copied ? 'check' : 'content_copy'}
      </span>
      <span className={styles.messageCopyLabel}>
        {copied ? 'Copiado' : 'Copiar'}
      </span>
    </button>
  )
}
