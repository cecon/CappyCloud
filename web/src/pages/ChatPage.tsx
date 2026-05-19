import { Fragment, type Dispatch, type SetStateAction, type UIEvent, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
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
  'text/plain',
  'text/markdown',
  'application/pdf',
  'application/json',
  'application/xml',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
])
const ALLOWED_ATTACHMENT_EXT = new Set([
  '.png',
  '.jpg',
  '.jpeg',
  '.webp',
  '.gif',
  '.txt',
  '.md',
  '.markdown',
  '.log',
  '.json',
  '.yaml',
  '.yml',
  '.csv',
  '.xml',
  '.pdf',
  '.docx',
])
const MAX_IMAGE_ATTACHMENT_BYTES = 8 * 1024 * 1024
const MAX_ARTIFACT_ATTACHMENT_BYTES = 50 * 1024 * 1024
const IMAGE_ONLY_PROMPT =
  'Analise a imagem anexada, descreva o erro visível e indique os próximos passos.'

const STICKY_SCROLL_THRESHOLD_PX = 96
const CHAT_PREFS_KEY = 'cappycloud.chat.preferences.v1'
const CHAT_CONVERSATIONS_COLLAPSED_KEY = 'cappycloud.chat.conversationsCollapsed'
const CONVERSATION_PAGE_SIZE = 6

type RepoChatPreference = {
  branch?: string
  modelId?: string
}

type ChatPreferenceState = {
  lastRepoSlug?: string
  lastModelId?: string
  byRepo?: Record<string, RepoChatPreference>
}

function fileExtension(name: string): string {
  const idx = name.lastIndexOf('.')
  return idx >= 0 ? name.slice(idx).toLowerCase() : ''
}

function isSupportedAttachment(file: File): boolean {
  return (
    ALLOWED_ATTACHMENT_MIME.has(file.type) ||
    file.type.startsWith('text/') ||
    ALLOWED_ATTACHMENT_EXT.has(fileExtension(file.name))
  )
}

function isImageFile(file: File): boolean {
  const ext = fileExtension(file.name)
  return file.type.startsWith('image/') || ['.png', '.jpg', '.jpeg', '.webp', '.gif'].includes(ext)
}

function attachmentLimitBytes(file: File): number {
  return isImageFile(file) ? MAX_IMAGE_ATTACHMENT_BYTES : MAX_ARTIFACT_ATTACHMENT_BYTES
}

function attachmentValidationError(file: File): string | null {
  if (!isSupportedAttachment(file)) return 'Tipo não suportado'
  const limit = attachmentLimitBytes(file)
  if (file.size > limit) return `Acima de ${(limit / 1024 / 1024).toFixed(0)} MB`
  return null
}

function clipboardImageName(file: File, index: number): string {
  if (file.name.trim()) return file.name
  if (!file.type.startsWith('image/')) return `anexo-${index + 1}`
  if (file.type === 'image/jpeg') return `print-${index + 1}.jpg`
  if (file.type === 'image/webp') return `print-${index + 1}.webp`
  if (file.type === 'image/gif') return `print-${index + 1}.gif`
  return `print-${index + 1}.png`
}

function normalizedClipboardFile(file: File, index: number): File {
  const name = clipboardImageName(file, index)
  if (name === file.name) return file
  return new File([file], name, {
    type: file.type || 'application/octet-stream',
    lastModified: file.lastModified || Date.now(),
  })
}

function isVisionModel(model: AiModel | undefined): boolean {
  return !!model?.capabilities?.includes('vision')
}

function preferredVisionModelId(models: AiModel[]): string {
  const visionModels = models.filter((model) => isVisionModel(model))
  return (
    visionModels.find((model) => model.is_default?.vision)?.model_id ||
    sortModelsForSelect(visionModels)[0]?.model_id ||
    ''
  )
}

function modelIdForAttachments(
  models: AiModel[],
  selectedModelId: string,
  hasImage: boolean,
): string {
  if (!hasImage) return selectedModelId
  const selected = models.find((model) => model.model_id === selectedModelId)
  if (isVisionModel(selected)) return selectedModelId
  return preferredVisionModelId(models) || selectedModelId
}

function isSendableTrayItem(item: TrayItem): boolean {
  return item.kind === 'pending' || item.kind === 'uploaded'
}

function trayItemHasImage(item: TrayItem): boolean {
  if (item.kind === 'pending') return isImageFile(item.file)
  if (item.kind === 'uploaded') {
    return item.attachment.kind === 'image' || item.attachment.mime_type.startsWith('image/')
  }
  return false
}

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

function formatShortDuration(ms: number): string {
  if (ms < 1000) return 'menos de 1s'
  const seconds = Math.floor(ms / 1000)
  if (seconds < 60) return `${seconds}s`
  const minutes = Math.floor(seconds / 60)
  const rest = seconds - minutes * 60
  return rest > 0 ? `${minutes}m ${rest}s` : `${minutes}m`
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

function readChatPrefs(): ChatPreferenceState {
  try {
    const raw = window.localStorage.getItem(CHAT_PREFS_KEY)
    if (!raw) return {}
    const parsed = JSON.parse(raw)
    return parsed && typeof parsed === 'object' ? parsed : {}
  } catch {
    return {}
  }
}

function updateChatPrefs(update: (prefs: ChatPreferenceState) => ChatPreferenceState): void {
  try {
    const next = update(readChatPrefs())
    window.localStorage.setItem(CHAT_PREFS_KEY, JSON.stringify(next))
  } catch {
    // Preferência local não deve bloquear o chat.
  }
}

function defaultTextModelId(models: AiModel[]): string {
  return models.find((m) => m.is_default?.text)?.model_id || models[0]?.model_id || ''
}

function validModelId(models: AiModel[], modelId?: string): string {
  if (!modelId) return ''
  return models.some((model) => model.model_id === modelId) ? modelId : ''
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

type ActivityTrace = {
  content: string
  steps: ThoughtStep[]
  elapsedMs: number
  interrupted?: boolean
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
  const stageDone = event.state === 'done'

  return previous.map((stage, index) => {
    const nextStage = stages[index] ?? stage
    if (index < currentIndex) {
      return { ...stage, label: nextStage.label, status: 'done' }
    }
    if (index === currentIndex) {
      return {
        ...stage,
        label: nextStage.label,
        status: stageDone ? 'done' : 'active',
        detail: event.message,
      }
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

function updateActivityTrace(
  prev: Record<string, ActivityTrace>,
  anchor: SessionProgressAnchor | null,
  updater: (steps: ThoughtStep[]) => ThoughtStep[],
): Record<string, ActivityTrace> {
  if (!anchor) return prev
  const current = prev[anchor.id] ?? { content: anchor.content, steps: [], elapsedMs: 0 }
  return {
    ...prev,
    [anchor.id]: {
      ...current,
      content: anchor.content,
      steps: updater(current.steps),
    },
  }
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
  const [conversationSearch, setConversationSearch] = useState('')
  const [visibleConversationCount, setVisibleConversationCount] = useState(CONVERSATION_PAGE_SIZE)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [messagesLoading, setMessagesLoading] = useState(false)
  const [messagesError, setMessagesError] = useState<string | null>(null)
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [loading, setLoading] = useState(true)

  const [workspaces, setWorkspaces] = useState<Workspace[]>([])
  const [selectedSlug, setSelectedSlug] = useState<string>('')
  const [selectedBranch, setSelectedBranch] = useState<string>('')
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
  const [streamActivityAt, setStreamActivityAt] = useState<number | null>(null)
  const [streamElapsedMs, setStreamElapsedMs] = useState(0)
  const [pendingAction, setPendingAction] = useState<ActionRequiredEvent | null>(null)
  const [sessionProgress, setSessionProgress] = useState<SessionStageState[]>([])
  const [sessionProgressAnchor, setSessionProgressAnchor] = useState<SessionProgressAnchor | null>(null)
  const [activityTraces, setActivityTraces] = useState<Record<string, ActivityTrace>>({})
  const [conversationsCollapsed, setConversationsCollapsed] = useState(() => {
    try {
      return window.localStorage.getItem(CHAT_CONVERSATIONS_COLLAPSED_KEY) === 'true'
    } catch {
      return false
    }
  })
  const conversationsToggleIcon = conversationsCollapsed
    ? 'keyboard_double_arrow_right'
    : 'keyboard_double_arrow_left'

  // Anexos pendentes de envio (uploads em curso, concluídos ou falhados).
  // Apenas itens `kind === 'uploaded'` viajam no payload do streamAssistantReply.
  const [trayItems, setTrayItems] = useState<TrayItem[]>([])
  const [isDragOver, setIsDragOver] = useState(false)
  const fileInputRef = useRef<HTMLInputElement | null>(null)

  /**
   * Faz upload de anexos/artefatos, registando placeholders na tray enquanto
   * a Promise resolve. Sem conversa ativa, mantém os arquivos como pendentes
   * para a primeira mensagem da tela inicial.
   */
  const uploadFiles = useCallback(
    (files: File[]) => {
      if (files.length === 0) return
      const normalized = files.map((file, index) => normalizedClipboardFile(file, index))
      const hasImage = normalized.some(isImageFile)
      const modelForImages = modelIdForAttachments(models, selectedModelId, hasImage)
      if (modelForImages && modelForImages !== selectedModelId) {
        setSelectedModelId(modelForImages)
      }

      for (const file of normalized) {
        const validationError = attachmentValidationError(file)
        if (validationError) {
          setTrayItems((prev) => [
            ...prev,
            {
              kind: 'failed',
              localId: randomId(),
              filename: file.name,
              error: validationError,
            },
          ])
          continue
        }

        if (!activeId) {
          setTrayItems((prev) => [
            ...prev,
            {
              kind: 'pending',
              localId: randomId(),
              filename: file.name,
              file,
            },
          ])
          continue
        }

        const localId = randomId()
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
    [activeId, models, selectedModelId, token],
  )

  const uploadPendingAttachments = useCallback(
    async (conversationId: string): Promise<string[]> => {
      const pending = trayItems.filter(
        (item): item is Extract<TrayItem, { kind: 'pending' }> => item.kind === 'pending',
      )
      const attachmentIds: string[] = []
      for (const item of pending) {
        const ctrl = new AbortController()
        setTrayItems((prev) =>
          prev.map((it) =>
            it.localId === item.localId
              ? {
                  kind: 'uploading',
                  localId: item.localId,
                  filename: item.filename,
                  abort: () => ctrl.abort(),
                }
              : it,
          ),
        )
        try {
          const att = await uploadAttachment(token, conversationId, item.file, ctrl.signal)
          attachmentIds.push(att.id)
          setTrayItems((prev) =>
            prev.map((it) =>
              it.localId === item.localId
                ? { kind: 'uploaded', localId: item.localId, attachment: att }
                : it,
            ),
          )
        } catch (e) {
          setTrayItems((prev) =>
            prev.map((it) =>
              it.localId === item.localId
                ? {
                    kind: 'failed',
                    localId: item.localId,
                    filename: item.filename,
                    error: e instanceof Error ? e.message : String(e),
                  }
                : it,
            ),
          )
          throw e
        }
      }
      return attachmentIds
    },
    [token, trayItems],
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

  const abortControllerRef = useRef<AbortController | null>(null)
  const stopRequestedRef = useRef(false)
  const optimisticConversationIdRef = useRef<string | null>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const chatPrefsRef = useRef<ChatPreferenceState>(readChatPrefs())
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
    try {
      window.localStorage.setItem(
        CHAT_CONVERSATIONS_COLLAPSED_KEY,
        String(conversationsCollapsed),
      )
    } catch {
      // Preferência visual local não deve bloquear o chat.
    }
  }, [conversationsCollapsed])

  useEffect(() => {
    setVisibleConversationCount(CONVERSATION_PAGE_SIZE)
  }, [conversationSearch])

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
        if (cancelled) return

        const prefs = chatPrefsRef.current
        let preferredSlug = prefs.lastRepoSlug || ''

        if (wsList.status === 'fulfilled') {
          setWorkspaces(wsList.value)
          if (preferredSlug && !wsList.value.some((workspace) => workspace.slug === preferredSlug)) {
            preferredSlug = ''
          }
          if (preferredSlug) {
            setSelectedSlug(preferredSlug)
            setSelectedBranch(prefs.byRepo?.[preferredSlug]?.branch || '')
          }
        } else if (wsList.reason instanceof AuthError) {
          setToken(null)
          window.location.href = '/login'
          return
        }

        if (modelsList.status === 'fulfilled') {
          const ms = modelsList.value
          setModels(ms)
          const preferredModel =
            validModelId(ms, preferredSlug ? prefs.byRepo?.[preferredSlug]?.modelId : undefined) ||
            validModelId(ms, prefs.lastModelId) ||
            defaultTextModelId(ms)
          if (preferredModel) setSelectedModelId(preferredModel)
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
    if (!selectedSlug) return
    const prefs = readChatPrefs()
    const branch = prefs.byRepo?.[selectedSlug]?.branch || ''
    setSelectedBranch((prev) => (prev === branch ? prev : branch))
    if (models.length > 0) {
      const modelId = validModelId(models, prefs.byRepo?.[selectedSlug]?.modelId)
      if (modelId) setSelectedModelId((prev) => (prev === modelId ? prev : modelId))
    }
  }, [selectedSlug, models])

  useEffect(() => {
    if (!selectedSlug) return
    updateChatPrefs((prefs) => {
      const byRepo = { ...(prefs.byRepo || {}) }
      byRepo[selectedSlug] = { ...(byRepo[selectedSlug] || {}), branch: selectedBranch || undefined }
      return { ...prefs, lastRepoSlug: selectedSlug, byRepo }
    })
  }, [selectedSlug, selectedBranch])

  useEffect(() => {
    if (!selectedModelId) return
    updateChatPrefs((prefs) => {
      const byRepo = { ...(prefs.byRepo || {}) }
      if (selectedSlug) {
        byRepo[selectedSlug] = { ...(byRepo[selectedSlug] || {}), modelId: selectedModelId }
      }
      return { ...prefs, lastModelId: selectedModelId, byRepo }
    })
  }, [selectedModelId, selectedSlug])

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
    const preserveOptimistic = optimisticConversationIdRef.current === activeId
    setDiffStats(null)
    setDiff(null)
    setPrUrl(null)
    setHeadBranch(null)
    if (!preserveOptimistic) {
      setMessages([])
      setMessagesLoading(true)
    } else {
      setMessagesLoading(false)
    }
    setMessagesError(null)
    setLiveUsage(null)
    ;(async () => {
      try {
        const [msgs, usage] = await Promise.all([
          fetchMessages(token, activeId),
          fetchConversationUsage(token, activeId),
        ])
        if (!cancelled) {
          setMessages((prev) =>
            preserveOptimistic && msgs.length === 0 && prev.length > 0 ? prev : msgs,
          )
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
    if (stopRequestedRef.current) return
    stopRequestedRef.current = true
    const elapsedMs = streamStartedAt ? Date.now() - streamStartedAt : streamElapsedMs
    const anchor = sessionProgressAnchor
    const conversationId = activeId
    const cancelPromise = conversationId
      ? cancelConversation(token, conversationId)
      : Promise.resolve(false)
    abortControllerRef.current?.abort()
    setStreamStartedAt(null)
    if (anchor) {
      setActivityTraces((prev) => ({
        ...prev,
        [anchor.id]: {
          ...(prev[anchor.id] ?? { content: anchor.content, steps: [], elapsedMs: 0 }),
          content: anchor.content,
          elapsedMs,
          interrupted: true,
        },
      }))
      setMessages((m) => {
        const alreadyNotified = m.some(
          (msg) =>
            msg.role === 'assistant' &&
            msg.content === '_Execução interrompida antes da resposta final._',
        )
        if (alreadyNotified) return m
        return [
          ...m,
          {
            id: randomId(),
            role: 'assistant',
            content: '_Execução interrompida antes da resposta final._',
            created_at: new Date().toISOString(),
          },
        ]
      })
    }
    setStreaming(false)
    setPendingAction(null)
    setStreamActivityAt(null)
    try {
      await cancelPromise
    } finally {
      stopRequestedRef.current = false
    }
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
    setTrayItems([])
    setIsDragOver(false)
    setActiveId(null)
    setMessages([])
    setMessagesError(null)
    setMessagesLoading(false)
    setSessionProgressAnchor(null)
    setStreamActivityAt(null)
    setTimeout(() => inputRef.current?.focus(), 50)
  }

  /** Seleciona uma conversa histórica sem deixar o streaming atual contaminar a UI. */
  function handleSelectConversation(conversationId: string) {
    if (conversationId === activeId) return
    abortControllerRef.current?.abort()
    abortControllerRef.current = null
    setStreaming(false)
    setThoughtSteps([])
    setStreamActivityAt(null)
    setPendingAction(null)
    setSessionProgress([])
    setSessionProgressAnchor(null)
    setActivityTraces({})
    setInput('')
    setSidePanel('none')
    setActiveId(conversationId)
    closeMobile()
  }

  /** Cria conversa e envia a mensagem inicial de uma vez */
  async function handleNewChatWithMessage(text: string) {
    const sendableAttachments = trayItems.filter(isSendableTrayItem)
    const userText = text.trim() || (sendableAttachments.length ? IMAGE_ONLY_PROMPT : '')
    if (!userText) return
    const modelForRequest = modelIdForAttachments(
      models,
      selectedModelId,
      sendableAttachments.some(trayItemHasImage),
    )
    if (modelForRequest && modelForRequest !== selectedModelId) {
      setSelectedModelId(modelForRequest)
    }
    const repos = selectedSlug
      ? [{ slug: selectedSlug, base_branch: selectedBranch || null }]
      : []
    const c = await createConversation(token, repos)
    // Update otimista do título — o backend renomeia "Nova conversa" para o
    // início da primeira mensagem (mesma lógica de _TITLE_MAX_LEN=80).
    const previewTitle =
      userText.length > 80 ? userText.slice(0, 80) + '…' : userText
    const cWithTitle = { ...c, title: previewTitle }
    optimisticConversationIdRef.current = c.id
    setConversations((prev) => [cWithTitle, ...prev])
    setActiveId(c.id)
    setMessages([])
    setInput('')

    setStreaming(true)
    setThoughtSteps([])
    lastTextOffsetRef.current = 0
    const startedAt = Date.now()
    setStreamStartedAt(startedAt)
    setStreamActivityAt(startedAt)
    setStreamElapsedMs(0)
    setPendingAction(null)
    setSessionProgress(createSessionProgress('initializing'))

    const ctrl = new AbortController()
    abortControllerRef.current = ctrl

    const userMsg: ChatMessage = {
      id: randomId(),
      role: 'user',
      content: userText,
      created_at: new Date().toISOString(),
    }
    setSessionProgressAnchor({ id: userMsg.id, content: userMsg.content })
    setActivityTraces((prev) => ({
      ...prev,
      [userMsg.id]: { content: userMsg.content, steps: [], elapsedMs: 0 },
    }))
    setMessages([userMsg])

    try {
      const uploadedAttachmentIds = await uploadPendingAttachments(c.id)
      await streamAssistantReply(token, c.id, userText, {
        onText(accumulated) {
          setStreamActivityAt(Date.now())
          const delta = accumulated.slice(lastTextOffsetRef.current)
          lastTextOffsetRef.current = accumulated.length
          if (delta) {
            setThoughtSteps((prev) => appendTextToThoughts(prev, delta))
            setActivityTraces((prev) =>
              updateActivityTrace(prev, userMsg, (steps) => appendTextToThoughts(steps, delta)),
            )
          }
        },
        onToolStart(tool) {
          setStreamActivityAt(Date.now())
          setThoughtSteps((prev) => appendToolStartToThoughts(prev, tool))
          setActivityTraces((prev) =>
            updateActivityTrace(prev, userMsg, (steps) => appendToolStartToThoughts(steps, tool)),
          )
        },
        onToolResult(result) {
          setStreamActivityAt(Date.now())
          setThoughtSteps((prev) => applyToolResultToThoughts(prev, result))
          setActivityTraces((prev) =>
            updateActivityTrace(prev, userMsg, (steps) => applyToolResultToThoughts(steps, result)),
          )
        },
        onActionRequired(action) { setStreamActivityAt(Date.now()); setPendingAction(action) },
        onStatus(status) {
          setStreamActivityAt(Date.now())
          const statusWithMode = { ...status, mode: status.mode ?? 'initializing' }
          setSessionProgress((prev) =>
            reduceSessionProgress(
              prev.length ? prev : createSessionProgress(statusWithMode.mode),
              statusWithMode,
            )
          )
        },
        onError(message) {
          setStreamActivityAt(Date.now())
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
        onDone(usage) { setStreamActivityAt(Date.now()); setLiveUsage(usage) },
        signal: ctrl.signal,
      }, modelForRequest || null, uploadedAttachmentIds.length ? uploadedAttachmentIds : null)
      setStreamStartedAt(null)
      setStreamActivityAt(null)
      setActivityTraces((prev) => ({
        ...prev,
        [userMsg.id]: {
          ...(prev[userMsg.id] ?? { content: userMsg.content, steps: [], elapsedMs: 0 }),
          content: userMsg.content,
          elapsedMs: Date.now() - startedAt,
        },
      }))
      clearTrayLocal()
      const [msgs, totals] = await Promise.all([
        fetchMessages(token, c.id),
        fetchConversationUsage(token, c.id),
      ])
      setMessages(msgs)
      optimisticConversationIdRef.current = null
      setConvUsage(totals)
      setLiveUsage(null)
      setSessionProgress([])
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
      setStreamActivityAt(null)
      abortControllerRef.current = null
      fetchConversationDiff(token, c.id).then((d) => setDiffStats(d.stats)).catch(() => {})
    }
  }

  async function handleSend(textOverride?: string) {
    if (!activeId || streaming) return

    // Bloqueia envio enquanto houver uploads em curso para não perder o
    // anexo no meio do streaming. Failed items podem ficar — o utilizador
    // já viu o erro e decide se remove ou tenta de novo.
    if (trayItems.some((it) => it.kind === 'uploading')) return
    const sendableAttachments = trayItems.filter(isSendableTrayItem)
    const text = (textOverride ?? input).trim() ||
      (sendableAttachments.length ? IMAGE_ONLY_PROMPT : '')
    if (!text) return
    const modelForRequest = modelIdForAttachments(
      models,
      selectedModelId,
      sendableAttachments.some(trayItemHasImage),
    )
    if (modelForRequest && modelForRequest !== selectedModelId) {
      setSelectedModelId(modelForRequest)
    }
    const uploadedAttachmentIds = trayItems
      .filter((it): it is Extract<TrayItem, { kind: 'uploaded' }> => it.kind === 'uploaded')
      .map((it) => it.attachment.id)

    if (!textOverride) setInput('')
    setStreaming(true)
    setThoughtSteps([])
    lastTextOffsetRef.current = 0
    const startedAt = Date.now()
    setStreamStartedAt(startedAt)
    setStreamActivityAt(startedAt)
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
    setActivityTraces((prev) => ({
      ...prev,
      [userMsg.id]: { content: userMsg.content, steps: [], elapsedMs: 0 },
    }))
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
      const pendingAttachmentIds = await uploadPendingAttachments(activeId)
      const attachmentIds = [...uploadedAttachmentIds, ...pendingAttachmentIds]
      await streamAssistantReply(token, activeId, text, {
        onText(accumulated) {
          setStreamActivityAt(Date.now())
          const delta = accumulated.slice(lastTextOffsetRef.current)
          lastTextOffsetRef.current = accumulated.length
          if (delta) {
            setThoughtSteps((prev) => appendTextToThoughts(prev, delta))
            setActivityTraces((prev) =>
              updateActivityTrace(prev, userMsg, (steps) => appendTextToThoughts(steps, delta)),
            )
          }
        },
        onToolStart(tool) {
          setStreamActivityAt(Date.now())
          setThoughtSteps((prev) => appendToolStartToThoughts(prev, tool))
          setActivityTraces((prev) =>
            updateActivityTrace(prev, userMsg, (steps) => appendToolStartToThoughts(steps, tool)),
          )
        },
        onToolResult(result) {
          setStreamActivityAt(Date.now())
          setThoughtSteps((prev) => applyToolResultToThoughts(prev, result))
          setActivityTraces((prev) =>
            updateActivityTrace(prev, userMsg, (steps) => applyToolResultToThoughts(steps, result)),
          )
        },
        onActionRequired(action) { setStreamActivityAt(Date.now()); setPendingAction(action) },
        onStatus(status) {
          setStreamActivityAt(Date.now())
          const statusWithMode = { ...status, mode: status.mode ?? 'initializing' }
          setSessionProgress((prev) =>
            reduceSessionProgress(
              prev.length ? prev : createSessionProgress(statusWithMode.mode),
              statusWithMode,
            )
          )
        },
        onError(message) {
          setStreamActivityAt(Date.now())
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
        onDone(usage) { setStreamActivityAt(Date.now()); setLiveUsage(usage) },
        signal: ctrl.signal,
      }, modelForRequest || null, attachmentIds.length ? attachmentIds : null)
      setStreamStartedAt(null)
      setStreamActivityAt(null)
      setActivityTraces((prev) => ({
        ...prev,
        [userMsg.id]: {
          ...(prev[userMsg.id] ?? { content: userMsg.content, steps: [], elapsedMs: 0 }),
          content: userMsg.content,
          elapsedMs: Date.now() - startedAt,
        },
      }))
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
      setStreamActivityAt(null)
      abortControllerRef.current = null
      if (activeId) fetchConversationDiff(token, activeId).then((d) => setDiffStats(d.stats)).catch(() => {})
    }
  }

  function handleActionReply(reply: string) { handleSend(reply) }

  const activeConv = conversations.find((c) => c.id === activeId)
  const activeEnvSlug = activeConv?.repos?.[0]?.slug ?? null
  const showThinking =
    streaming &&
    !sessionProgress.length &&
    thoughtSteps.length === 0 &&
    !pendingAction

  const normalizedConversationSearch = conversationSearch.trim().toLocaleLowerCase('pt-BR')
  const filteredConversations = useMemo(() => {
    if (!normalizedConversationSearch) return conversations

    return conversations.filter((conversation) => {
      const repoText = conversation.repos
        ?.map((repo) => [repo.slug, repo.alias, repo.base_branch].filter(Boolean).join(' '))
        .join(' ') ?? ''
      const searchableText = `${conversation.title} ${repoText}`.toLocaleLowerCase('pt-BR')

      return searchableText.includes(normalizedConversationSearch)
    })
  }, [conversations, normalizedConversationSearch])
  const visibleConversations = useMemo(
    () => filteredConversations.slice(0, visibleConversationCount),
    [filteredConversations, visibleConversationCount],
  )
  const hiddenConversationCount = Math.max(
    filteredConversations.length - visibleConversations.length,
    0,
  )
  const streamIdleMs = streaming && streamActivityAt
    ? Math.max(0, Date.now() - streamActivityAt)
    : 0
  const sidebarConversationCountLabel = normalizedConversationSearch
    ? `${filteredConversations.length} de ${conversations.length} sessões`
    : hiddenConversationCount > 0
      ? `${visibleConversations.length} de ${conversations.length} sessões`
      : `${conversations.length} sessões`
  const groups = groupConversations(visibleConversations)
  const handleConversationListScroll = useCallback((event: UIEvent<HTMLDivElement>) => {
    if (hiddenConversationCount <= 0) return

    const list = event.currentTarget
    const distanceToBottom = list.scrollHeight - list.scrollTop - list.clientHeight
    if (distanceToBottom > 80) return

    setVisibleConversationCount((count) =>
      Math.min(count + CONVERSATION_PAGE_SIZE, filteredConversations.length),
    )
  }, [filteredConversations.length, hiddenConversationCount])

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
        {/* ── Conversation panel ───────────────────────────────── */}
        <aside
          className={`${styles.sidebar} ${conversationsCollapsed ? styles.sidebarCollapsed : ''} ${mobileOpened ? styles.sidebarOpen : ''}`}
        >
          <div className={styles.sidebarHead}>
            <div className={styles.sidebarHeadLeft}>
              <div>
                <div className={styles.sidebarTitle}>Conversas</div>
                <div className={styles.sidebarSubtitle}>{sidebarConversationCountLabel}</div>
              </div>
            </div>
            <button
              type="button"
              className={styles.panelCollapseBtn}
              onClick={() => setConversationsCollapsed((prev) => !prev)}
              title={conversationsCollapsed ? 'Expandir conversas' : 'Recolher conversas'}
              aria-label={conversationsCollapsed ? 'Expandir conversas' : 'Recolher conversas'}
            >
              <span className={styles.icon}>{conversationsToggleIcon}</span>
            </button>
            <Burger opened={mobileOpened} onClick={toggleMobile} size="sm" color="var(--cc-on-surface-variant)" hiddenFrom="sm" />
          </div>

          {/* New session button */}
          <div className={styles.sidebarActions}>
            <button className={styles.newSessionBtn} onClick={handleNewChat}>
              <span className={styles.icon}>add</span>
              <span>Nova Sessão</span>
              <span className={styles.kbdHint}>⌘N</span>
            </button>
            <div className={styles.sessionSearch} role="search">
              <span className={styles.icon}>search</span>
              <input
                value={conversationSearch}
                onChange={(event) => setConversationSearch(event.currentTarget.value)}
                placeholder="Buscar conversas"
                aria-label="Buscar conversas"
              />
              {conversationSearch && (
                <button
                  type="button"
                  className={styles.sessionSearchClear}
                  onClick={() => setConversationSearch('')}
                  title="Limpar busca"
                  aria-label="Limpar busca"
                >
                  <span className={styles.icon}>close</span>
                </button>
              )}
            </div>
          </div>

          <button
            type="button"
            className={styles.collapsedConversationsBtn}
            onClick={() => setConversationsCollapsed(false)}
            title="Expandir conversas"
            aria-label="Expandir conversas"
          >
            <span className={styles.icon}>forum</span>
            <span className={styles.collapsedCount}>{conversations.length}</span>
          </button>

          <div className={styles.sessionList} onScroll={handleConversationListScroll}>
            {groups.length === 0 && (
              <p className={styles.emptyHint}>
                {conversations.length === 0 ? 'Nenhuma conversa ainda.' : 'Nenhuma conversa encontrada.'}
              </p>
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
            {hiddenConversationCount > 0 && (
              <div className={styles.sessionListFooter}>
                <button
                  type="button"
                  className={styles.loadMoreSessionsBtn}
                  onClick={() => setVisibleConversationCount((count) => count + CONVERSATION_PAGE_SIZE)}
                >
                  <span>Carregar mais</span>
                  <span className={styles.loadMoreCount}>{hiddenConversationCount}</span>
                </button>
              </div>
            )}
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
            models={sortedModels}
            selectedModelId={selectedModelId}
            setSelectedModelId={setSelectedModelId}
            token={token}
            trayItems={trayItems}
            onPickFiles={handleFileSelection}
            onPasteFiles={handlePaste}
            onRemoveTrayItem={removeTrayItem}
            fileInputRef={fileInputRef}
            isDragOver={isDragOver}
            setDragOver={setIsDragOver}
          />
          ) : (
            <ActiveChat
              messages={messages}
              messagesLoading={messagesLoading}
              messagesError={messagesError}
              sessionProgressAnchor={sessionProgressAnchor}
              thoughtSteps={thoughtSteps}
              activityTraces={activityTraces}
              streamElapsedMs={streamElapsedMs}
              streamIdleMs={streamIdleMs}
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
              activeEnvSlug={activeEnvSlug}
              activeEnvName={workspaces.find(w => w.slug === activeEnvSlug)?.name ?? activeEnvSlug ?? workspaces[0]?.name ?? null}
              activeBaseBranch={activeConv?.repos?.[0]?.base_branch ?? null}
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
  setSelectedBranch: Dispatch<SetStateAction<string>>
  models: AiModel[]
  selectedModelId: string
  setSelectedModelId: (id: string) => void
  token: string
  trayItems: TrayItem[]
  onPickFiles: (files: FileList | null | undefined) => void
  onPasteFiles: (e: React.ClipboardEvent<HTMLTextAreaElement>) => void
  onRemoveTrayItem: (localId: string) => void
  fileInputRef: React.RefObject<HTMLInputElement | null>
  isDragOver: boolean
  setDragOver: (v: boolean) => void
}

function EmptyState({
  input, setInput, inputRef, onExecute, streaming,
  workspaces, selectedSlug, setSelectedSlug,
  selectedBranch, setSelectedBranch,
  models, selectedModelId, setSelectedModelId, token,
  trayItems, onPickFiles, onPasteFiles, onRemoveTrayItem, fileInputRef, isDragOver, setDragOver,
}: EmptyStateProps) {
  const [branches, setBranches] = useState<string[]>([])
  const [loadedSlug, setLoadedSlug] = useState('')
  const branchesLoading = !!selectedSlug && loadedSlug !== selectedSlug

  // auto-clone trata o caso de repo não clonado
  const hasSendableAttachment = trayItems.some(isSendableTrayItem)
  const hasUploadInProgress = trayItems.some((item) => item.kind === 'uploading')
  const canExecute =
    !!selectedSlug &&
    !!selectedBranch &&
    (!!input.trim() || hasSendableAttachment) &&
    !hasUploadInProgress &&
    !streaming

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
  const selectedWorkspaceName =
    workspaces.find((workspace) => workspace.slug === selectedSlug)?.name ?? 'Escolha o repositório'
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
            Escolha o repositório, descreva a tarefa e acompanhe execução, ferramentas,
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

      {/* Premium Command Bar */}
      <div
        className={`${styles.commandBarWrapper} ${isDragOver ? styles.commandBarWrapperDragOver : ''}`}
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
        <div className={styles.commandBarGlow} />
        <div className={styles.commandBar}>
          <div className={styles.commandBarInner}>
            <input
              ref={fileInputRef}
              type="file"
              accept="image/png,image/jpeg,image/jpg,image/webp,image/gif,.txt,.md,.markdown,.log,.json,.yaml,.yml,.csv,.xml,.pdf,.docx"
              multiple
              style={{ display: 'none' }}
              onChange={(e) => {
                onPickFiles(e.target.files)
                if (e.target) e.target.value = ''
              }}
            />
            <AttachmentTray
              items={trayItems}
              token={token}
              conversationId={null}
              onRemove={onRemoveTrayItem}
            />
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
                      : 'Descreva o que o agente deve fazer ou cole um print…'
                }
                rows={2}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onPaste={onPasteFiles}
                onKeyDown={handleKey}
                disabled={streaming}
              />
            </div>

            <div className={styles.commandToolbar}>
              <div className={styles.commandToolbarLeft}>
                <button
                  className={styles.toolbarBtn}
                  title="Anexar imagem ou arquivo"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={streaming}
                  type="button"
                >
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
                    !selectedSlug ? 'Selecione um repositório' :
                    !selectedBranch ? 'Selecione uma branch' :
                    hasUploadInProgress ? 'Aguarde os anexos terminarem o envio…' :
                    !input.trim() && !hasSendableAttachment ? 'Digite uma mensagem ou cole um print' : undefined
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
          title={selectedWorkspaceName}
          desc="Sessões isoladas por worktree, prontas para diff e PR."
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
  activityTraces: Record<string, ActivityTrace>
  streamElapsedMs: number
  streamIdleMs: number
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
  activeEnvSlug: string | null
  activeEnvName: string | null
  activeBaseBranch: string | null
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
  messages, messagesLoading, messagesError, sessionProgressAnchor, thoughtSteps, activityTraces, streamElapsedMs, streamIdleMs, sessionProgress, pendingAction,
  showThinking, streaming, input, setInput, inputRef,
  onSend, onStop, onActionReply, activeEnvSlug, activeEnvName, activeBaseBranch,
  workspaces,
  diffStats, prLoading, prUrl, prError, headBranch, onCreatePr,
  activeTitle: _activeTitle,
  token, conversationId, sidePanel, diff, diffLoading, onOpenDiff, onToggleFiles,
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

  let sessionProgressBeforeIndex = -1
  if (sessionProgressAnchor) {
    for (let index = messages.length - 1; index >= 0; index -= 1) {
      const message = messages[index]
      if (
        message.id === sessionProgressAnchor.id ||
        (message.role === 'user' && message.content === sessionProgressAnchor.content)
      ) {
        sessionProgressBeforeIndex = index
        break
      }
    }
    if (sessionProgressBeforeIndex < 0) {
      for (let index = messages.length - 1; index >= 0; index -= 1) {
        if (messages[index].role === 'user') {
          sessionProgressBeforeIndex = index
          break
        }
      }
    }
  }

  const tracesByContent = Object.values(activityTraces)
  const activityTraceFor = (message: ChatMessage): ActivityTrace | null => {
    if (message.role !== 'user') return null
    return activityTraces[message.id]
      ?? tracesByContent.find((trace) => trace.content === message.content)
      ?? null
  }
  const hasSendableAttachment = trayItems.some(isSendableTrayItem)
  const hasUploadInProgress = trayItems.some((item) => item.kind === 'uploading')

  return (
    <div className={styles.activeChat}>
      {/* Session header — env + branch + diff stats + PR + painel ficheiros/diff */}
      <div className={styles.sessionHeader}>
        <div className={styles.sessionHeaderInner}>
          <div className={styles.sessionHeaderLeft}>
          {activeEnvSlug ? (
            <>
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
              {activeEnvSlug && (
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
              {!messagesLoading && !messagesError && messages.length === 0 && !streaming && (
                <div className={styles.chatStateCard}>
                  <Text size="sm" c="dimmed">Esta conversa ainda não tem mensagens.</Text>
                </div>
              )}
              {sessionProgress.length > 0 && sessionProgressBeforeIndex < 0 && (
                <SessionProgressCard
                  stages={sessionProgress}
                  elapsedMs={streamElapsedMs}
                  idleMs={streamIdleMs}
                />
              )}
              {messages.map((m, index) => (
                <Fragment key={m.id}>
                  {sessionProgress.length > 0 && index === sessionProgressBeforeIndex && (
                    <SessionProgressCard
                      stages={sessionProgress}
                      elapsedMs={streamElapsedMs}
                      idleMs={streamIdleMs}
                    />
                  )}
                  <PaperMessage
                    key={m.id}
                    role={m.role}
                    content={m.content}
                    modelUsed={m.model_used ?? null}
                    promptTokens={m.prompt_tokens ?? 0}
                    completionTokens={m.completion_tokens ?? 0}
                    costUsd={m.cost_usd ?? 0}
                  />
                  {activityTraceFor(m)?.steps.length ? (
                    <ThinkingStream
                      steps={activityTraceFor(m)!.steps}
                      streaming={streaming && sessionProgressAnchor?.content === m.content}
                      elapsedMs={
                        streaming && sessionProgressAnchor?.content === m.content
                          ? streamElapsedMs
                          : activityTraceFor(m)!.elapsedMs
                      }
                      idleMs={
                        streaming && sessionProgressAnchor?.content === m.content
                          ? streamIdleMs
                          : 0
                      }
                      interrupted={!!activityTraceFor(m)!.interrupted}
                    />
                  ) : null}
                </Fragment>
              ))}
              {((thoughtSteps.length > 0 && !sessionProgressAnchor) || (streaming && showThinking)) && (
                <Stack gap="xs">
                  {thoughtSteps.length > 0 && !sessionProgressAnchor && (
                    <ThinkingStream
                      steps={thoughtSteps}
                      streaming={streaming}
                      elapsedMs={streamElapsedMs}
                      idleMs={streamIdleMs}
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
            accept="image/png,image/jpeg,image/jpg,image/webp,image/gif,.txt,.md,.markdown,.log,.json,.yaml,.yml,.csv,.xml,.pdf,.docx"
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
            title="Anexar imagem ou arquivo da conversa"
            aria-label="Anexar imagem ou arquivo"
          >
            <span className={styles.icon}>attachment</span>
          </button>
          <textarea
            ref={inputRef}
            className={styles.chatTextarea}
            placeholder={
              isDragOver
                ? 'Solte para anexar à conversa…'
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
              (!input.trim() && !pendingAction && !hasSendableAttachment) ||
              (streaming && !pendingAction) ||
              hasUploadInProgress
            }
            title={
              hasUploadInProgress
                ? 'Aguarde os anexos terminarem o envio…'
                : !input.trim() && !pendingAction && hasSendableAttachment
                  ? 'Enviar imagem anexada'
                : undefined
            }
          >
            <span className={styles.icon}>keyboard_return</span>
          </button>
          )}
          </div>

          {/* Context status bar — repo + branch */}
          <div className={styles.chatContextBar}>
          <div className={styles.chatContextPill}>
            <span className={`${styles.icon} ${styles.chatContextIcon}`}>source</span>
            <span className={styles.chatContextText}>
              {activeEnvName ?? activeEnvSlug ?? workspaces[0]?.name ?? '—'}
            </span>
          </div>
          {activeBaseBranch && (
            <div className={styles.chatContextPill} style={{ marginLeft: '0.35rem' }}>
              <span className={`${styles.icon} ${styles.chatContextIcon}`}>fork_right</span>
              <span className={styles.chatContextText}>
                {headBranch ?? activeBaseBranch}
              </span>
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
          <span
            className={styles.chatContextText}
            style={{ opacity: 0.35, fontSize: '0.7rem', marginLeft: '0.5rem' }}
            title="Para mudar repositório ou branch, crie uma Nova Sessão"
          >
            · fixo
          </span>
          </div>
        </div>
      </div>
    </div>
  )
}

/** Card com progresso operacional da criação da sessão e execução do agente. */
function SessionProgressCard({
  stages,
  elapsedMs,
  idleMs,
}: {
  stages: SessionStageState[]
  elapsedMs: number
  idleMs: number
}) {
  const completed = stages.every((stage) => stage.status === 'done')
  const doneCount = stages.filter((s) => s.status === 'done').length
  const progressPct = stages.length > 0 ? (doneCount / stages.length) * 100 : 0
  const activeStage = stages.find((stage) => stage.status === 'active')
  const title = completed
    ? 'Sistema ligado'
    : activeStage?.key === 'agent'
      ? 'Agente trabalhando'
      : 'Ligando sistema'
  const meta = completed
    ? `Concluído em ${formatShortDuration(elapsedMs)}`
    : `Em andamento há ${formatShortDuration(elapsedMs)}`
  const idleLabel = !completed && activeStage?.key === 'agent' && idleMs >= 5000
    ? `sem novos eventos há ${formatShortDuration(idleMs)}`
    : null

  return (
    <div
      className={`${styles.sessionProgressCard} ${
        completed ? styles.sessionProgressCardComplete : ''
      }`}
      style={{ ['--cc-progress' as string]: `${progressPct}%` }}
    >
      <div
        className={styles.sessionProgressHeader}
        aria-live={completed ? 'off' : 'polite'}
      >
        <span
          className={`${styles.sessionProgressBootIcon} ${
            completed ? styles.sessionProgressBootIconDone : ''
          }`}
          aria-hidden="true"
        >
          {completed ? '✓' : ''}
        </span>
        <span className={styles.sessionProgressHeaderText}>
          <span>{title}</span>
          <span className={styles.sessionProgressMeta}>
            {meta}{idleLabel ? ` · ${idleLabel}` : ''}
          </span>
        </span>
      </div>
      <div className={styles.sessionProgressList}>
        {stages.map((stage, index) => (
          <div
            key={stage.key}
            className={styles.sessionProgressItem}
            style={{ ['--cc-step-delay' as string]: `${Math.min(index, 6) * 45}ms` }}
          >
            <span
              className={`${styles.sessionProgressIcon} ${
                stage.status === 'active'
                  ? styles.sessionProgressIconActive
                  : stage.status === 'done'
                    ? styles.sessionProgressIconDone
                    : ''
              }`}
              aria-hidden="true"
            >
              {stage.status === 'done' ? '✓' : ''}
            </span>
            <span className={styles.sessionProgressStepBody}>
              <span
                className={`${styles.sessionProgressLabel} ${
                  stage.status === 'done' ? styles.sessionProgressLabelDone : ''
                }`}
              >
                {stage.label}
              </span>
              {stage.detail && (
                <span className={styles.sessionProgressDetail}>
                  {stage.detail}
                </span>
              )}
            </span>
          </div>
        ))}
      </div>
      {!completed && <div className={styles.sessionProgressPulse} aria-hidden="true" />}
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
  const totalTokens = (promptTokens ?? 0) + (completionTokens ?? 0)
  const hasUsage =
    !isUser && (totalTokens > 0 || !!modelUsed)
  const costLabel = totalTokens === 0 && (costUsd ?? 0) === 0
    ? 'uso não informado'
    : formatCostUsd(costUsd ?? 0)
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
          {totalTokens > 0 && (
            <span className={styles.messageUsageTokens}>
              {(promptTokens ?? 0).toLocaleString('pt-BR')} in · {(completionTokens ?? 0).toLocaleString('pt-BR')} out
            </span>
          )}
          <span className={styles.messageUsageCost}>{costLabel}</span>
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
