import { Fragment, type Dispatch, type SetStateAction, type UIEvent, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Burger,
  ScrollArea,
  Stack,
  Text,
} from '@/components/ui/legacy'
import { useDisclosure } from '@/components/ui/legacy'
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
  executeSlashCommand,
  fetchSandboxes,
  fetchUserPreferences,
  fetchWorkspaces,
  DEFAULT_PERMISSION_MODE,
  getToken,
  listSlashCommands,
  redirectToLogin,
  streamAssistantReply,
  updateUserPreferences,
  uploadAttachment,
  errorToUserMessage,
  type ActionRequiredEvent,
  type AiModel,
  type ChatMessage,
  type CommandResultEvent,
  type CommandStartEvent,
  type Conversation,
  type ConversationUsage,
  type CurrentUser,
  type DoneEvent,
  type PayloadSizeBreakdown,
  type PermissionMode,
  type Sandbox,
  type SlashCommand,
  type StatusEvent,
  type Workspace,
} from '../api'
import { ActionRequiredCard } from '../components/ActionRequiredCard'
import { AttachmentTray, type TrayItem } from '../components/AttachmentTray'
import { ModelPicker } from '../components/ModelPicker'
import { ThinkingIndicator } from '../components/ThinkingIndicator'
import { ThinkingStream, type ThoughtStep } from '../components/ThinkingStream'
import { CommandConfirmation } from '../components/chat/CommandConfirmation'
import { SlashCommandMenu } from '../components/chat/SlashCommandMenu'
import { slashCommandQuery, shouldOpenSlashCommands } from '../components/chat/SlashCommandMenu.utils'
import { CappyIcon } from '../components/layout/icons'
import { roleFromUser, visibleNavigationItems, type NavigationItem } from '../components/layout/navigation'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '../components/ui/dropdown-menu'
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from '../components/ui/select'
import { useCurrentUser } from '../hooks/useCurrentUser'
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
type ChatMainMode = 'chat' | 'sandboxes'

type PermissionModeOption = {
  value: PermissionMode
  label: string
  icon: string
  description: string
  tone?: 'safe' | 'warn' | 'danger'
}

const PERMISSION_MODE_OPTIONS: PermissionModeOption[] = [
  {
    value: 'request_permissions',
    label: 'Perguntar antes de agir',
    icon: 'shield',
    description: 'O agente pede confirmação para alterar algo',
    tone: 'safe',
  },
  {
    value: 'accept_edits',
    label: 'Aceitar edições',
    icon: 'edit_note',
    description: 'Alterações propostas podem ser aplicadas',
    tone: 'warn',
  },
  {
    value: 'plan',
    label: 'Modo de planejamento',
    icon: 'rule',
    description: 'Responde e planeja sem executar mudanças',
    tone: 'safe',
  },
  {
    value: 'auto',
    label: 'Modo automático',
    icon: 'bolt',
    description: 'Executa sem pedir, use com cuidado',
    tone: 'warn',
  },
  {
    value: 'bypass_permissions',
    label: 'Acesso completo',
    icon: 'warning',
    description: 'Permite executar ações sem pedir confirmação',
    tone: 'danger',
  },
]

const PERMISSION_MODE_VALUES = new Set<PermissionMode>(
  PERMISSION_MODE_OPTIONS.map((option) => option.value),
)

function normalizePermissionMode(value: unknown): PermissionMode {
  return typeof value === 'string' && PERMISSION_MODE_VALUES.has(value as PermissionMode)
    ? (value as PermissionMode)
    : DEFAULT_PERMISSION_MODE
}

function permissionModeOption(mode: PermissionMode): PermissionModeOption {
  return PERMISSION_MODE_OPTIONS.find((option) => option.value === mode) ?? PERMISSION_MODE_OPTIONS[0]
}

function fallbackReasonLabel(reason?: string): string {
  const normalized = (reason || '').replace(/[_-]+/g, ' ').trim()
  return normalized || 'runtime model changed'
}

type RepoChatPreference = {
  branch?: string
  modelId?: string
}

type ChatPreferenceState = {
  lastRepoSlug?: string
  lastModelId?: string
  byRepo?: Record<string, RepoChatPreference>
}

function userInitials(email?: string | null): string {
  if (!email) return 'CC'
  const [name] = email.split('@')
  const parts = name.split(/[._-]+/).filter(Boolean)
  if (parts.length >= 2) return `${parts[0][0]}${parts[1][0]}`.toUpperCase()
  return name.slice(0, 2).toUpperCase()
}

function userRoleLabel(user: { role?: string; is_super_admin?: boolean } | null): string {
  if (!user) return 'Conta'
  if (user.is_super_admin) return 'Super admin'
  if (user.role === 'admin') return 'Administrador'
  return 'Usuário'
}

function SidebarUserMenuLink({ item }: { item: NavigationItem }) {
  return (
    <DropdownMenuItem asChild>
      <Link to={item.to}>
        <CappyIcon name={item.icon} className="size-4" />
        <span>{item.label}</span>
      </Link>
    </DropdownMenuItem>
  )
}

function SidebarUserMenu({ user }: { user: CurrentUser | null }) {
  const role = roleFromUser(user)
  const primary = visibleNavigationItems(role, 'primary')
  const work = visibleNavigationItems(role, 'work')
  const admin = visibleNavigationItems(role, 'admin')
  const account = visibleNavigationItems(role, 'account')

  function logout() {
    redirectToLogin()
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button type="button" className={styles.sidebarUserCard} aria-label="Abrir menu do usuário">
          <span className={styles.sidebarUserAvatar}>
            {userInitials(user?.email)}
          </span>
          <span className={styles.sidebarUserMeta}>
            <span className={styles.sidebarUserName}>
              {user?.email ?? 'CappyCloud'}
            </span>
            <span className={styles.sidebarUserRole}>
              {userRoleLabel(user)}
            </span>
          </span>
          <span className={`${styles.icon} ${styles.sidebarUserChevron}`}>expand_more</span>
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" side="right" sideOffset={10} className="w-72">
        <DropdownMenuLabel>
          <span className="block truncate text-sm text-foreground">{user?.email ?? 'Conta'}</span>
          <span className="block text-xs font-normal text-muted-foreground">{userRoleLabel(user)}</span>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        {primary.map((item) => <SidebarUserMenuLink key={item.to} item={item} />)}
        <DropdownMenuSeparator />
        <DropdownMenuLabel>Trabalho</DropdownMenuLabel>
        {work.map((item) => <SidebarUserMenuLink key={item.to} item={item} />)}
        {admin.length > 0 && (
          <>
            <DropdownMenuSeparator />
            <DropdownMenuLabel>Administracao</DropdownMenuLabel>
            {admin.map((item) => <SidebarUserMenuLink key={item.to} item={item} />)}
          </>
        )}
        <DropdownMenuSeparator />
        <DropdownMenuLabel>Conta</DropdownMenuLabel>
        {account.map((item) => <SidebarUserMenuLink key={item.to} item={item} />)}
        <DropdownMenuItem onClick={logout}>
          <CappyIcon name="logout" className="size-4" />
          Sair
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
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
  pre({ children }) {
    return <>{children}</>
  },
  code({ className, children, ...props }) {
    const rawCode = String(children ?? '').replace(/\n$/, '')
    const match = /language-(\w+)/.exec(className ?? '')
    const language = match?.[1]
    const hasBlockBreak = rawCode.includes('\n')

    if (!hasBlockBreak && !language) {
      return (
        <code className={className} {...props}>
          {children}
        </code>
      )
    }

    return (
      <CodeBlockCard
        code={rawCode}
        language={language ?? 'text'}
      />
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
  if (!tool.id || !tool.name) return prev
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
  if (!result.id) return prev
  return prev.map((step) =>
    step.kind === 'tool' && step.id === result.id
      ? { ...step, output: result.output, isError: result.is_error, done: true }
      : step,
  )
}

function commandThoughtId(command: string): string {
  return `command:${command || 'unknown'}`
}

function appendCommandStartToThoughts(prev: ThoughtStep[], event: CommandStartEvent): ThoughtStep[] {
  const id = commandThoughtId(event.command)
  if (prev.some((step) => step.kind === 'tool' && step.id === id)) return prev
  return [
    ...prev,
    {
      kind: 'tool',
      id,
      name: event.command || 'comando',
      input: event.label,
      done: false,
    },
  ]
}

function applyCommandResultToThoughts(prev: ThoughtStep[], event: CommandResultEvent): ThoughtStep[] {
  const id = commandThoughtId(event.command)
  const isError =
    event.status === 'failed' ||
    event.status === 'cancelled' ||
    event.status === 'unavailable'
  const output = event.details_markdown || event.summary
  const updated = prev.map((step) =>
    step.kind === 'tool' && step.id === id
      ? { ...step, output, isError, done: true }
      : step,
  )
  if (updated !== prev && updated.some((step) => step.kind === 'tool' && step.id === id)) {
    return updated
  }
  return [
    ...prev,
    {
      kind: 'tool',
      id,
      name: event.command || 'comando',
      input: 'Comando do chat',
      output,
      isError,
      done: true,
    },
  ]
}

function finishPendingThoughtTools(prev: ThoughtStep[], isError = false): ThoughtStep[] {
  return prev.map((step) =>
    step.kind === 'tool' && !step.done
      ? {
          ...step,
          done: true,
          isError: isError || step.isError,
          output: step.output ?? '',
        }
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
  const currentUserState = useCurrentUser()
  const currentUser = currentUserState.status === 'ready' ? currentUserState.user : null
  const [mobileOpened, { toggle: toggleMobile, close: closeMobile }] = useDisclosure()

  const [conversations, setConversations] = useState<Conversation[]>([])
  const [activeId, setActiveId] = useState<string | null>(null)
  const [mainMode, setMainMode] = useState<ChatMainMode>('chat')
  const [conversationSearch, setConversationSearch] = useState('')
  const [visibleConversationCount, setVisibleConversationCount] = useState(CONVERSATION_PAGE_SIZE)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [messagesLoading, setMessagesLoading] = useState(false)
  const [messagesError, setMessagesError] = useState<string | null>(null)
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [loading, setLoading] = useState(true)
  const [userDefaultPermissionMode, setUserDefaultPermissionMode] =
    useState<PermissionMode>(DEFAULT_PERMISSION_MODE)
  const [permissionMode, setPermissionModeState] = useState<PermissionMode>(DEFAULT_PERMISSION_MODE)
  const [permissionWarningRuntimeConfirmed, setPermissionWarningRuntimeConfirmed] = useState(false)

  const [workspaces, setWorkspaces] = useState<Workspace[]>([])
  const [sandboxes, setSandboxes] = useState<Sandbox[]>([])
  const [selectedSandboxId, setSelectedSandboxId] = useState<string>('')
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
  const availableSandboxes = useMemo(() => sandboxes.filter(isSandboxAvailable), [sandboxes])
  const selectedSandbox = useMemo(
    () => sandboxes.find((sandbox) => sandbox.id === selectedSandboxId) ?? null,
    [sandboxes, selectedSandboxId],
  )
  const selectableWorkspaces = useMemo(() => {
    if (!selectedSandboxId) return workspaces
    return workspaces.filter((workspace) => workspace.sandbox_id === selectedSandboxId)
  }, [selectedSandboxId, workspaces])

  const [thoughtSteps, setThoughtSteps] = useState<ThoughtStep[]>([])
  const [streamStartedAt, setStreamStartedAt] = useState<number | null>(null)
  const [streamActivityAt, setStreamActivityAt] = useState<number | null>(null)
  const [streamElapsedMs, setStreamElapsedMs] = useState(0)
  const [pendingAction, setPendingAction] = useState<ActionRequiredEvent | null>(null)
  const [sessionProgress, setSessionProgress] = useState<SessionStageState[]>([])
  const [sessionProgressAnchor, setSessionProgressAnchor] = useState<SessionProgressAnchor | null>(null)
  const [activityTraces, setActivityTraces] = useState<Record<string, ActivityTrace>>({})
  const [conversationsCollapsed, setConversationsCollapsed] = useState(false)

  const setPermissionMode = useCallback(
    (mode: PermissionMode) => {
      if (streaming) return
      setPermissionModeState(mode)
      setUserDefaultPermissionMode(mode)
      setPermissionWarningRuntimeConfirmed(false)
      updateUserPreferences(token, { default_permission_mode: mode })
        .then((prefs) =>
          setUserDefaultPermissionMode(normalizePermissionMode(prefs.default_permission_mode)),
        )
        .catch(() => {})
      if (!activeId) return
      setConversations((prev) =>
        prev.map((conversation) =>
          conversation.id === activeId
            ? { ...conversation, permission_mode: mode }
            : conversation,
        ),
      )
    },
    [activeId, streaming, token],
  )

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

  /** Limpa a tray sem chamar DELETE; anexos ficam vinculados ao historico. */
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
  /** Comprimento do `accumulated` text ja aplicado na timeline thoughtSteps. */
  const lastTextOffsetRef = useRef(0)
  const lastStreamCursorRef = useRef<number | null>(null)

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

  const activeConversationPermissionMode = useMemo(() => {
    const activeConversation = activeId
      ? conversations.find((conversation) => conversation.id === activeId)
      : null
    return activeConversation
      ? normalizePermissionMode(activeConversation.permission_mode)
      : userDefaultPermissionMode
  }, [activeId, conversations, userDefaultPermissionMode])

  useEffect(() => {
    setPermissionModeState(activeConversationPermissionMode)
    setPermissionWarningRuntimeConfirmed(false)
  }, [activeId, activeConversationPermissionMode])

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const [convsResult, wsList, modelsList, userPrefsResult, sandboxesResult] = await Promise.allSettled([
          fetchConversations(token),
          fetchWorkspaces(token),
          fetchAiModels(token),
          fetchUserPreferences(token),
          fetchSandboxes(token),
        ])
        if (cancelled) return

        const prefs = chatPrefsRef.current
        let preferredSlug = prefs.lastRepoSlug || ''

        if (userPrefsResult.status === 'fulfilled') {
          const mode = normalizePermissionMode(userPrefsResult.value.default_permission_mode)
          setUserDefaultPermissionMode(mode)
          setPermissionModeState(mode)
        } else if (userPrefsResult.reason instanceof AuthError) {
          redirectToLogin()
          return
        }

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
          redirectToLogin()
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
          redirectToLogin()
          return
        }

        if (sandboxesResult.status === 'fulfilled') {
          setSandboxes(sandboxesResult.value)
        } else if (sandboxesResult.reason instanceof AuthError) {
          redirectToLogin()
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
    if (sandboxes.length === 0) {
      setSelectedSandboxId('')
      return
    }
    const currentIsValid = sandboxes.some(
      (sandbox) => sandbox.id === selectedSandboxId && isSandboxAvailable(sandbox),
    )
    if (currentIsValid) return

    const repoSandboxId = workspaces.find((workspace) => workspace.slug === selectedSlug)?.sandbox_id
    const repoSandboxIsValid =
      !!repoSandboxId &&
      sandboxes.some((sandbox) => sandbox.id === repoSandboxId && isSandboxAvailable(sandbox))
    const fallback = availableSandboxes[0]?.id ?? ''
    setSelectedSandboxId(repoSandboxIsValid ? repoSandboxId : fallback)
  }, [availableSandboxes, sandboxes, selectedSandboxId, selectedSlug, workspaces])

  useEffect(() => {
    if (!selectedSandboxId || !selectedSlug) return
    const selectedWorkspace = workspaces.find((workspace) => workspace.slug === selectedSlug)
    if (selectedWorkspace?.sandbox_id === selectedSandboxId) return
    setSelectedSlug('')
    setSelectedBranch('')
  }, [selectedSandboxId, selectedSlug, workspaces])

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
          redirectToLogin()
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

  const handleNewChat = useCallback(() => {
    setMainMode('chat')
    setTrayItems([])
    setIsDragOver(false)
    setActiveId(null)
    setMessages([])
    setMessagesError(null)
    setMessagesLoading(false)
    setSessionProgressAnchor(null)
    setStreamActivityAt(null)
    setPermissionModeState(userDefaultPermissionMode)
    setPermissionWarningRuntimeConfirmed(false)
    setTimeout(() => inputRef.current?.focus(), 50)
  }, [userDefaultPermissionMode])

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === 'n') {
        e.preventDefault()
        handleNewChat()
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [handleNewChat])

  /** Seleciona uma conversa histórica sem deixar o streaming atual contaminar a UI. */
  function handleSelectConversation(conversationId: string) {
    setMainMode('chat')
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
    setPermissionWarningRuntimeConfirmed(false)
    setActiveId(conversationId)
    closeMobile()
  }

  /** Cria conversa e envia a mensagem inicial de uma vez */
  async function handleNewChatWithMessage(text: string) {
    const selectedPermissionMode = permissionMode
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
    const c = await createConversation(
      token,
      repos,
      modelForRequest || null,
      selectedSandboxId || null,
    )
    // Update otimista do título — o backend renomeia "Nova conversa" para o
    // início da primeira mensagem (mesma lógica de _TITLE_MAX_LEN=80).
    const previewTitle =
      userText.length > 80 ? userText.slice(0, 80) + '…' : userText
    const cWithTitle = { ...c, title: previewTitle, permission_mode: selectedPermissionMode }
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
    setPermissionWarningRuntimeConfirmed(false)

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
    let latestPayloadDiagnostics: PayloadSizeBreakdown | null = null

    try {
      const uploadedAttachmentIds = await uploadPendingAttachments(c.id)
      await streamAssistantReply(
        token,
        c.id,
        userText,
        {
          onCursor(cursor) { lastStreamCursorRef.current = cursor },
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
          onCommandStart(event) {
            setStreamActivityAt(Date.now())
            setThoughtSteps((prev) => appendCommandStartToThoughts(prev, event))
            setActivityTraces((prev) =>
              updateActivityTrace(prev, userMsg, (steps) => appendCommandStartToThoughts(steps, event)),
            )
          },
          onCommandResult(event) {
            setStreamActivityAt(Date.now())
            setThoughtSteps((prev) => applyCommandResultToThoughts(prev, event))
            setActivityTraces((prev) =>
              updateActivityTrace(prev, userMsg, (steps) => applyCommandResultToThoughts(steps, event)),
            )
          },
          onActionRequired(action) {
            setStreamActivityAt(Date.now())
            setPendingAction(action)
            abortControllerRef.current?.abort()
          },
          onStatus(status) {
            setStreamActivityAt(Date.now())
            if (status.metadata?.permission_warning?.runtime_confirmed) {
              setPermissionWarningRuntimeConfirmed(true)
            }
            if (!status.stage) return
            const statusWithMode = { ...status, mode: status.mode ?? 'initializing' }
            setSessionProgress((prev) =>
              reduceSessionProgress(
                prev.length ? prev : createSessionProgress(statusWithMode.mode),
                statusWithMode,
              )
            )
          },
          onPayloadDiagnostic(diagnostics) {
            setStreamActivityAt(Date.now())
            latestPayloadDiagnostics = diagnostics
          },
          onError(message) {
            setStreamActivityAt(Date.now())
            setThoughtSteps((prev) => finishPendingThoughtTools(prev, true))
            setActivityTraces((prev) =>
              updateActivityTrace(prev, userMsg, (steps) => finishPendingThoughtTools(steps, true)),
            )
            setMessages((m) => [
              ...m,
              {
                id: randomId(),
                role: 'assistant',
                content: `**Erro:** ${message}`,
                created_at: new Date().toISOString(),
                payload_diagnostics: latestPayloadDiagnostics,
              },
            ])
          },
          onDone(usage) {
            setStreamActivityAt(Date.now())
            setLiveUsage(usage)
            setThoughtSteps((prev) => finishPendingThoughtTools(prev))
            setActivityTraces((prev) =>
              updateActivityTrace(prev, userMsg, (steps) => finishPendingThoughtTools(steps)),
            )
          },
          signal: ctrl.signal,
        },
        modelForRequest || null,
        uploadedAttachmentIds.length ? uploadedAttachmentIds : null,
        selectedPermissionMode,
        null,
        false,
      )
      setStreamStartedAt(null)
      setStreamActivityAt(null)
      setThoughtSteps((prev) => finishPendingThoughtTools(prev))
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
        redirectToLogin(); return
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
            payload_diagnostics: latestPayloadDiagnostics,
          },
        ])
      }
    } finally {
      setStreaming(false)
      setStreamStartedAt(null)
      setStreamActivityAt(null)
      setThoughtSteps((prev) => finishPendingThoughtTools(prev))
      abortControllerRef.current = null
      fetchConversationDiff(token, c.id).then((d) => setDiffStats(d.stats)).catch(() => {})
    }
  }

  async function handleSend(textOverride?: string, options?: { resumeAction?: boolean }) {
    const isActionResume = Boolean(options?.resumeAction && pendingAction && textOverride?.trim())
    if (!activeId || (streaming && !isActionResume)) return
    const selectedPermissionMode = permissionMode

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

    const resumeCursor = isActionResume ? lastStreamCursorRef.current : null
    if (!isActionResume) {
      lastStreamCursorRef.current = null
    }
    abortControllerRef.current?.abort()
    if (!textOverride) setInput('')
    setStreaming(true)
    if (!isActionResume) {
      setThoughtSteps([])
    }
    lastTextOffsetRef.current = 0
    const startedAt = Date.now()
    setStreamStartedAt(startedAt)
    setStreamActivityAt(startedAt)
    setStreamElapsedMs(0)
    setPendingAction(null)
    if (!isActionResume) {
      setSessionProgress([])
    }
    setPermissionWarningRuntimeConfirmed(false)

    const ctrl = new AbortController()
    abortControllerRef.current = ctrl

    const userMsg: ChatMessage = {
      id: randomId(),
      role: 'user',
      content: text,
      created_at: new Date().toISOString(),
    }
    if (!isActionResume) {
      setSessionProgressAnchor({ id: userMsg.id, content: userMsg.content })
      setActivityTraces((prev) => ({
        ...prev,
        [userMsg.id]: { content: userMsg.content, steps: [], elapsedMs: 0 },
      }))
      setMessages((m) => [...m, userMsg])
    }
    let latestPayloadDiagnostics: PayloadSizeBreakdown | null = null

    // Renomeia título se ainda for o default — bate com o backend.
    if (!isActionResume) {
      setConversations((prev) =>
      prev.map((c) => {
        if (c.id !== activeId) return c
        if (c.title && c.title !== 'Nova conversa') return c
        const previewTitle = text.length > 80 ? text.slice(0, 80) + '…' : text
        return { ...c, title: previewTitle, permission_mode: selectedPermissionMode }
      }),
      )
    }

    try {
      const pendingAttachmentIds = isActionResume ? [] : await uploadPendingAttachments(activeId)
      const attachmentIds = isActionResume ? [] : [...uploadedAttachmentIds, ...pendingAttachmentIds]
      await streamAssistantReply(
        token,
        activeId,
        text,
        {
          onCursor(cursor) { lastStreamCursorRef.current = cursor },
          onText(accumulated) {
            setStreamActivityAt(Date.now())
            const delta = accumulated.slice(lastTextOffsetRef.current)
            lastTextOffsetRef.current = accumulated.length
            if (delta) {
              setThoughtSteps((prev) => appendTextToThoughts(prev, delta))
              if (!isActionResume) {
                setActivityTraces((prev) =>
                  updateActivityTrace(prev, userMsg, (steps) => appendTextToThoughts(steps, delta)),
                )
              }
            }
          },
          onToolStart(tool) {
            setStreamActivityAt(Date.now())
            setThoughtSteps((prev) => appendToolStartToThoughts(prev, tool))
            if (!isActionResume) {
              setActivityTraces((prev) =>
                updateActivityTrace(prev, userMsg, (steps) => appendToolStartToThoughts(steps, tool)),
              )
            }
          },
          onToolResult(result) {
            setStreamActivityAt(Date.now())
            setThoughtSteps((prev) => applyToolResultToThoughts(prev, result))
            if (!isActionResume) {
              setActivityTraces((prev) =>
                updateActivityTrace(prev, userMsg, (steps) => applyToolResultToThoughts(steps, result)),
              )
            }
          },
          onCommandStart(event) {
            setStreamActivityAt(Date.now())
            setThoughtSteps((prev) => appendCommandStartToThoughts(prev, event))
            if (!isActionResume) {
              setActivityTraces((prev) =>
                updateActivityTrace(prev, userMsg, (steps) => appendCommandStartToThoughts(steps, event)),
              )
            }
          },
          onCommandResult(event) {
            setStreamActivityAt(Date.now())
            setThoughtSteps((prev) => applyCommandResultToThoughts(prev, event))
            if (!isActionResume) {
              setActivityTraces((prev) =>
                updateActivityTrace(prev, userMsg, (steps) => applyCommandResultToThoughts(steps, event)),
              )
            }
          },
          onActionRequired(action) {
            setStreamActivityAt(Date.now())
            setPendingAction(action)
            abortControllerRef.current?.abort()
          },
          onStatus(status) {
            setStreamActivityAt(Date.now())
            if (status.metadata?.permission_warning?.runtime_confirmed) {
              setPermissionWarningRuntimeConfirmed(true)
            }
            if (!status.stage) return
            const statusWithMode = { ...status, mode: status.mode ?? 'initializing' }
            setSessionProgress((prev) =>
              reduceSessionProgress(
                prev.length ? prev : createSessionProgress(statusWithMode.mode),
                statusWithMode,
              )
            )
          },
          onPayloadDiagnostic(diagnostics) {
            setStreamActivityAt(Date.now())
            latestPayloadDiagnostics = diagnostics
          },
          onError(message) {
            setStreamActivityAt(Date.now())
            setThoughtSteps((prev) => finishPendingThoughtTools(prev, true))
            if (!isActionResume) {
              setActivityTraces((prev) =>
                updateActivityTrace(prev, userMsg, (steps) => finishPendingThoughtTools(steps, true)),
              )
            }
            setMessages((m) => [
              ...m,
              {
                id: randomId(),
                role: 'assistant',
                content: `**Erro:** ${message}`,
                created_at: new Date().toISOString(),
                payload_diagnostics: latestPayloadDiagnostics,
              },
            ])
          },
          onDone(usage) {
            setStreamActivityAt(Date.now())
            setLiveUsage(usage)
            setThoughtSteps((prev) => finishPendingThoughtTools(prev))
            if (!isActionResume) {
              setActivityTraces((prev) =>
                updateActivityTrace(prev, userMsg, (steps) => finishPendingThoughtTools(steps)),
              )
            }
          },
          signal: ctrl.signal,
        },
        modelForRequest || null,
        attachmentIds.length ? attachmentIds : null,
        selectedPermissionMode,
        resumeCursor,
        isActionResume,
      )
      setStreamStartedAt(null)
      setStreamActivityAt(null)
      setThoughtSteps((prev) => finishPendingThoughtTools(prev))
      if (!isActionResume) {
        setActivityTraces((prev) => ({
          ...prev,
          [userMsg.id]: {
            ...(prev[userMsg.id] ?? { content: userMsg.content, steps: [], elapsedMs: 0 }),
            content: userMsg.content,
            elapsedMs: Date.now() - startedAt,
          },
        }))
        clearTrayLocal()
      }
      const [msgs, totals] = await Promise.all([
        fetchMessages(token, activeId),
        fetchConversationUsage(token, activeId),
      ])
      setMessages(msgs)
      setConvUsage(totals)
      setLiveUsage(null)
    } catch (e) {
      if (e instanceof AuthError) {
        redirectToLogin(); return
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
            payload_diagnostics: latestPayloadDiagnostics,
          },
        ])
      }
    } finally {
      setStreaming(false)
      setStreamStartedAt(null)
      setStreamActivityAt(null)
      setThoughtSteps((prev) => finishPendingThoughtTools(prev))
      abortControllerRef.current = null
      if (activeId) fetchConversationDiff(token, activeId).then((d) => setDiffStats(d.stats)).catch(() => {})
    }
  }

  function handleActionReply(reply: string) { void handleSend(reply, { resumeAction: true }) }

  const activeConv = conversations.find((c) => c.id === activeId)
  const activeEnvSlug = activeConv?.repos?.[0]?.slug ?? null
  const activeSandboxName =
    sandboxes.find((sandbox) => sandbox.id === activeConv?.sandbox_id)?.name ??
    selectedSandbox?.name ??
    null
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
  const activeSandboxCount = sandboxes.filter(isSandboxAvailable).length
  const sandboxAccessCount = activeSandboxCount
  const streamIdleMs = streaming && streamActivityAt
    ? Math.max(0, Date.now() - streamActivityAt)
    : 0
  const sidebarConversationCountLabel = normalizedConversationSearch
    ? `${filteredConversations.length} de ${conversations.length} sessões`
    : hiddenConversationCount > 0
      ? `${visibleConversations.length} de ${conversations.length} sessões`
      : `${conversations.length} sessões`
  void sidebarConversationCountLabel
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
              <img src="/capybara.png" alt="" className={styles.sidebarLogo} />
              <div>
                <div className={styles.sidebarTitle}>CappyCloud</div>
                <div className={styles.sidebarSubtitle}>Workspace</div>
              </div>
            </div>
            <Burger opened={mobileOpened} onClick={toggleMobile} size="sm" color="var(--cc-on-surface-variant)" hiddenFrom="sm" />
          </div>

          {/* New session button */}
          <div className={styles.sidebarActions}>
            <button className={styles.newSessionBtn} onClick={handleNewChat}>
              <span className={styles.icon}>add</span>
              <span>Nova conversa</span>
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

          <div className={styles.sidebarUtility}>
            <button
              type="button"
              className={`${styles.sandboxAccessBtn} ${mainMode === 'sandboxes' ? styles.sandboxAccessBtnActive : ''}`}
              onClick={() => {
                setMainMode('sandboxes')
                closeMobile()
              }}
            >
              <span className={`${styles.icon} ${styles.sandboxAccessIcon}`}>dns</span>
              <span className={styles.sandboxAccessLabel}>Sandboxes & acessos</span>
              <span className={styles.sandboxAccessCount}>
                <span aria-hidden />
                {sandboxAccessCount}
              </span>
            </button>
          </div>

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
          <div className={styles.sidebarFooter}>
            <SidebarUserMenu user={currentUser} />
          </div>
        </aside>

        {/* ── Main ─────────────────────────────────────────────── */}
        <main className={styles.main}>
          {mainMode === 'sandboxes' ? (
            <SandboxAccessView
              sandboxes={sandboxes}
              workspaces={workspaces}
              conversations={conversations}
              onBackToChat={() => setMainMode('chat')}
            />
          ) : !activeId ? (
          <EmptyState
            input={input}
            setInput={setInput}
            inputRef={inputRef}
            onExecute={(text) => handleNewChatWithMessage(text)}
            streaming={streaming}
            sandboxes={availableSandboxes}
            selectedSandboxId={selectedSandboxId}
            setSelectedSandboxId={setSelectedSandboxId}
            selectableWorkspaces={selectableWorkspaces}
            selectedSlug={selectedSlug}
            setSelectedSlug={setSelectedSlug}
            selectedBranch={selectedBranch}
            setSelectedBranch={setSelectedBranch}
            permissionMode={permissionMode}
            setPermissionMode={setPermissionMode}
            permissionWarningRuntimeConfirmed={permissionWarningRuntimeConfirmed}
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
              activeSandboxName={activeSandboxName}
              sandboxAccessCount={sandboxAccessCount}
              diffStats={diffStats}
              prLoading={prLoading}
              prUrl={prUrl}
              prError={prError}
              headBranch={headBranch}
              onCreatePr={handleCreatePr}
              activeTitle={activeConv?.title ?? 'Conversa'}
              token={token}
              conversationId={activeId!}
              models={sortedModels}
              selectedModelId={selectedModelId}
              setSelectedModelId={setSelectedModelId}
              permissionMode={permissionMode}
              setPermissionMode={setPermissionMode}
              permissionWarningRuntimeConfirmed={permissionWarningRuntimeConfirmed}
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
function PermissionModeControl({
  value,
  onChange,
  disabled,
  runtimeConfirmed: _runtimeConfirmed,
  compact = false,
}: {
  value: PermissionMode
  onChange: (mode: PermissionMode) => void
  disabled: boolean
  runtimeConfirmed: boolean
  compact?: boolean
}) {
  const option = permissionModeOption(value)
  const pillTone =
    option.tone === 'danger'
      ? styles.permissionModePillHigh
      : option.tone === 'warn'
        ? styles.permissionModePillCaution
        : ''

  return (
    <div className={`${styles.permissionModeControl} ${compact ? styles.permissionModeControlCompact : ''}`}>
      <DropdownMenu>
        <DropdownMenuTrigger asChild disabled={disabled}>
          <button
            type="button"
            className={`${styles.permissionModePill} ${pillTone} ${disabled ? styles.permissionModePillDisabled : ''}`}
            title={disabled ? `${option.label} · bloqueado durante execução` : 'Modo de permissões'}
            aria-label="Modo de permissões"
            disabled={disabled}
          >
            <span className={`${styles.icon} ${styles.permissionModeIcon}`}>{option.icon}</span>
            <span className={styles.permissionModeLabel}>{option.label}</span>
            <span className={`${styles.icon} ${styles.permissionModeChevron}`}>expand_more</span>
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent
          align={compact ? 'start' : 'end'}
          sideOffset={8}
          className={styles.permissionModeMenu}
        >
          <DropdownMenuLabel className={styles.permissionModeMenuLabel}>
            Permissões do agente
          </DropdownMenuLabel>
          {PERMISSION_MODE_OPTIONS.map((mode) => {
            const selected = mode.value === value
            const toneClass =
              mode.tone === 'danger'
                ? styles.permissionModeMenuItemDanger
                : mode.tone === 'warn'
                  ? styles.permissionModeMenuItemWarn
                  : styles.permissionModeMenuItemSafe

            return (
              <DropdownMenuItem
                key={mode.value}
                className={`${styles.permissionModeMenuItem} ${toneClass} ${selected ? styles.permissionModeMenuItemSelected : ''}`}
                onClick={() => onChange(normalizePermissionMode(mode.value))}
              >
                <span className={`${styles.icon} ${styles.permissionModeMenuIcon}`}>{mode.icon}</span>
                <span className={styles.permissionModeMenuText}>
                  <span className={styles.permissionModeMenuTitle}>{mode.label}</span>
                  <span className={styles.permissionModeMenuDescription}>{mode.description}</span>
                </span>
              </DropdownMenuItem>
            )
          })}
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  )
}
interface EmptyStateProps {
  input: string
  setInput: (v: string) => void
  inputRef: React.RefObject<HTMLTextAreaElement | null>
  onExecute: (text: string) => void
  streaming: boolean
  selectableWorkspaces: Workspace[]
  sandboxes: Sandbox[]
  selectedSandboxId: string
  setSelectedSandboxId: (id: string) => void
  selectedSlug: string
  setSelectedSlug: (s: string) => void
  selectedBranch: string
  setSelectedBranch: Dispatch<SetStateAction<string>>
  permissionMode: PermissionMode
  setPermissionMode: (mode: PermissionMode) => void
  permissionWarningRuntimeConfirmed: boolean
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
  selectableWorkspaces, sandboxes, selectedSandboxId, setSelectedSandboxId,
  selectedSlug, setSelectedSlug,
  selectedBranch, setSelectedBranch,
  token,
  permissionMode, setPermissionMode, permissionWarningRuntimeConfirmed,
  trayItems, onPickFiles, onPasteFiles, onRemoveTrayItem, fileInputRef, isDragOver, setDragOver,
}: EmptyStateProps) {
  const [branches, setBranches] = useState<string[]>([])
  const [loadedSlug, setLoadedSlug] = useState('')
  const branchesLoading = !!selectedSlug && loadedSlug !== selectedSlug

  // auto-clone trata o caso de repo não clonado
  const hasSendableAttachment = trayItems.some(isSendableTrayItem)
  const hasUploadInProgress = trayItems.some((item) => item.kind === 'uploading')
  const sandboxRequired = !selectedSandboxId
  const canExecute =
    !sandboxRequired &&
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

  const repoRequired = selectableWorkspaces.length > 0 && !selectedSlug
  const branchRequired = !!selectedSlug && !selectedBranch

  return (
    <div className={styles.emptyState}>
      <section className={styles.welcomePanel}>
        <div className={styles.mascotWrapper}>
          <img src="/capybara.png" alt="CappyCloud" className={styles.mascot} />
          <div className={styles.mascotGlow} />
        </div>
        <div className={styles.welcomeCopy}>
          <h1 className={styles.welcomeTitle}>O que você quer descobrir hoje? </h1>
          <p className={styles.welcomeText}>
            Pergunte em português. O agente lê o <strong>repositório selecionado</strong> na sua cópia isolada
            e responde com passos, consultas e evidências.
          </p>
        </div>
      </section>

      <div className={styles.quickActions}>
        <QuickActionCard
          icon="search"
          iconColor="var(--cc-primary)"
          title="Consultar dados"
          desc="Me mostra o faturamento de ontem por forma de pagamento"
          onPick={setInput}
        />
        <QuickActionCard
          icon="bug_report"
          iconColor="var(--cc-error)"
          title="Investigar um bug"
          desc="O desconto não está batendo no cupom fiscal, por quê?? "
          onPick={setInput}
        />
        <QuickActionCard
          icon="library_books"
          iconColor="var(--cc-secondary)"
          title="Entender uma rotina"
          desc="Como funciona o fechamento de caixa no fim do dia?? "
          onPick={setInput}
        />
        <QuickActionCard
          icon="support_agent"
          iconColor="var(--muted-foreground)"
          title="Ajudar no suporte"
          desc="Cliente diz que a comanda sumiu, o que verifico?? "
          onPick={setInput}
        />
      </div>

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
                    ? 'Pergunte algo ao agente...'
                    : !selectedBranch
                      ? 'Selecione uma branch antes de continuar...'
                      : 'Pergunte algo ao agente... (Enter para enviar)'
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
                {sandboxes.length > 0 ? (
                  <Select
                    value={selectedSandboxId}
                    onValueChange={(id) => {
                      setSelectedSandboxId(id)
                      setSelectedSlug('')
                      setSelectedBranch('')
                    }}
                  >
                    <SelectTrigger
                      className={`${styles.contextSelectTrigger} ${styles.contextSelectTriggerSandbox} ${
                        sandboxRequired ? styles.contextPillRequired : ''
                      }`}
                      title="Selecionar sandbox"
                      aria-label="Selecionar sandbox"
                    >
                      <span className={styles.icon} aria-hidden="true">
                        dns
                      </span>
                      <SelectValue placeholder="Sandbox..." />
                    </SelectTrigger>
                    <SelectContent
                      className={styles.contextSelectContent}
                      position="item-aligned"
                    >
                      <SelectGroup>
                        <SelectLabel className={styles.contextSelectLabel}>
                          Sandbox
                        </SelectLabel>
                        {sandboxes.map((sandbox) => (
                          <SelectItem
                            key={sandbox.id}
                            value={sandbox.id}
                            className={styles.contextSelectItem}
                          >
                            {sandbox.name}
                          </SelectItem>
                        ))}
                      </SelectGroup>
                    </SelectContent>
                  </Select>
                ) : (
                  <div className={`${styles.contextPill} ${styles.contextPillRequired}`} style={{ marginLeft: '0.5rem' }}>
                    <span className={styles.icon} style={{ fontSize: '0.875rem', opacity: 0.5 }}>dns</span>
                    <span className={styles.contextPillLabel} style={{ opacity: 0.45 }}>Nenhuma sandbox</span>
                  </div>
                )}
                {selectableWorkspaces.length > 0 ? (
                  <Select
                    value={selectedSlug}
                    onValueChange={setSelectedSlug}
                  >
                    <SelectTrigger
                      className={`${styles.contextSelectTrigger} ${styles.contextSelectTriggerRepo} ${
                        repoRequired ? styles.contextPillRequired : ''
                      }`}
                      title="Selecionar repositório"
                      aria-label="Selecionar repositório"
                    >
                      <span className={styles.icon} aria-hidden="true">
                        source
                      </span>
                      <SelectValue placeholder="Repositório..." />
                    </SelectTrigger>
                    <SelectContent
                      className={styles.contextSelectContent}
                      position="item-aligned"
                    >
                      <SelectGroup>
                        <SelectLabel className={styles.contextSelectLabel}>
                          Repositório
                        </SelectLabel>
                        {selectableWorkspaces.map((w) => (
                          <SelectItem
                            key={w.slug}
                            value={w.slug}
                            className={styles.contextSelectItem}
                          >
                            {w.name}
                          </SelectItem>
                        ))}
                      </SelectGroup>
                    </SelectContent>
                  </Select>
                ) : (
                  <div className={`${styles.contextPill} ${styles.contextPillRequired}`} style={{ marginLeft: '0.5rem' }}>
                    <span className={styles.icon} style={{ fontSize: '0.875rem', opacity: 0.5 }}>source</span>
                    <span className={styles.contextPillLabel} style={{ opacity: 0.45 }}>Nenhum repositório</span>
                  </div>
                )}
                {selectedSlug && (
                  <Select
                    value={selectedBranch}
                    onValueChange={setSelectedBranch}
                    disabled={branchesLoading}
                  >
                    <SelectTrigger
                      className={`${styles.contextSelectTrigger} ${styles.contextSelectTriggerBranch} ${
                        branchRequired ? styles.contextPillRequired : ''
                      }`}
                      title="Selecionar branch"
                      aria-label="Selecionar branch"
                    >
                      <span className={styles.icon} aria-hidden="true">
                        fork_right
                      </span>
                      <SelectValue placeholder={branchesLoading ? '...' : 'Branch...'} />
                    </SelectTrigger>
                    <SelectContent
                      className={styles.contextSelectContent}
                      position="item-aligned"
                    >
                      <SelectGroup>
                        <SelectLabel className={styles.contextSelectLabel}>
                          Branch
                        </SelectLabel>
                        {branches.map((b) => (
                          <SelectItem
                            key={b}
                            value={b}
                            className={styles.contextSelectItem}
                          >
                            {b}
                          </SelectItem>
                        ))}
                      </SelectGroup>
                    </SelectContent>
                  </Select>
                )}
                <PermissionModeControl
                  value={permissionMode}
                  onChange={setPermissionMode}
                  disabled={streaming}
                  runtimeConfirmed={permissionWarningRuntimeConfirmed}
                />
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

      <p className={styles.emptyHint}>
        Você está numa cópia isolada — nada do que testar aqui afeta os outros usuários.
      </p>
    </div>
  )
}

/** Renderiza um atalho contextual da tela inicial do agente. */
function QuickActionCard({ icon, iconColor, title, desc, href, onPick }: {
  icon: string; iconColor: string; title: string; desc: string; href?: string; onPick?: (value: string) => void
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

  if (onPick) {
    return (
      <button type="button" className={styles.quickCardButton} onClick={() => onPick(desc)}>
        {content}
      </button>
    )
  }

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
  activeSandboxName: string | null
  sandboxAccessCount: number
  diffStats: { added: number; removed: number } | null
  prLoading: boolean
  prUrl: string | null
  prError: string | null
  headBranch: string | null
  onCreatePr: () => void
  activeTitle: string
  token: string
  conversationId: string
  models: AiModel[]
  selectedModelId: string
  setSelectedModelId: (id: string) => void
  permissionMode: PermissionMode
  setPermissionMode: (mode: PermissionMode) => void
  permissionWarningRuntimeConfirmed: boolean
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
  onSend, onStop, onActionReply, activeEnvSlug, activeEnvName, activeBaseBranch, activeSandboxName, sandboxAccessCount: _sandboxAccessCount,
  diffStats, prLoading, prUrl, prError, headBranch, onCreatePr,
  activeTitle: _activeTitle,
  token, conversationId,
  models, selectedModelId, setSelectedModelId,
  permissionMode, setPermissionMode, permissionWarningRuntimeConfirmed,
  convUsage, liveUsage,
  trayItems, onPickFiles, onPasteFiles, onRemoveTrayItem, fileInputRef, isDragOver, setDragOver,
}: ActiveChatProps) {
  const scrollRef = useRef<HTMLDivElement>(null)
  const shouldStickToBottomRef = useRef(true)
  const [elapsedSecs, setElapsedSecs] = useState(0)
  const [showJumpToLatest, setShowJumpToLatest] = useState(false)
  const [slashCommands, setSlashCommands] = useState<SlashCommand[]>([])
  const [slashOpen, setSlashOpen] = useState(false)
  const [slashQuery, setSlashQuery] = useState('')
  const [commandNotice, setCommandNotice] = useState<string | null>(null)
  const [confirmCommand, setConfirmCommand] = useState<{
    command: SlashCommand
    message: string
    confirmLabel: string
    cancelLabel: string
  } | null>(null)

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
    queueMicrotask(() => {
      setSlashOpen(false)
      setSlashQuery('')
      setSlashCommands([])
      setCommandNotice(null)
      setConfirmCommand(null)
    })
  }, [conversationId, selectedModelId, permissionMode])

  const openSlashCommands = useCallback((draft: string, caret: number) => {
    if (!shouldOpenSlashCommands(draft, caret) && !slashOpen) return
    setSlashQuery(slashCommandQuery(draft, caret))
    setSlashOpen(true)
    if (slashCommands.length === 0) {
      listSlashCommands(token, conversationId)
        .then((catalog) => setSlashCommands(catalog.commands))
        .catch(() => setCommandNotice('Nao foi possivel carregar comandos agora.'))
    }
  }, [conversationId, slashCommands.length, slashOpen, token])

  const runSlashCommand = useCallback(async (command: SlashCommand, confirmed = false) => {
    const unavailable =
      command.execution_mode === 'unavailable' ||
      command.availability.state === 'unavailable' ||
      command.availability.state === 'blocked'
    if (unavailable) {
      setCommandNotice(command.availability.reason || 'Comando indisponivel nesta conversa.')
      return
    }
    try {
      const response = await executeSlashCommand(token, conversationId, {
        command: command.name,
        confirmed,
        client_request_id: crypto.randomUUID(),
      })
      if (response.status === 'needs_confirmation' && response.confirmation) {
        setConfirmCommand({
          command,
          message: response.confirmation.message,
          confirmLabel: response.confirmation.confirm_label,
          cancelLabel: response.confirmation.cancel_label,
        })
        return
      }
      setCommandNotice(response.message || 'Comando enviado.')
      setConfirmCommand(null)
      setSlashOpen(false)
    } catch (error) {
      setCommandNotice(errorToUserMessage(error))
    }
  }, [conversationId, token])

  const pickSlashCommand = useCallback((command: SlashCommand) => {
    setSlashOpen(false)
    const unavailable =
      command.execution_mode === 'unavailable' ||
      command.availability.state === 'unavailable' ||
      command.availability.state === 'blocked'
    if (unavailable) {
      void runSlashCommand(command)
      return
    }
    if (command.requires_confirmation) {
      setConfirmCommand({
        command,
        message: command.confirmation_reason || 'Confirme a execucao do comando.',
        confirmLabel: 'Executar',
        cancelLabel: 'Cancelar',
      })
      return
    }
    void runSlashCommand(command)
  }, [runSlashCommand])

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
      ? (tracesByContent.find((trace) => trace.content === message.content) ?? null)
      : null
  }
  const hasSendableAttachment = trayItems.some(isSendableTrayItem)
  const hasUploadInProgress = trayItems.some((item) => item.kind === 'uploading')
  const selectedModelLabel =
    models.find((model) => model.id === selectedModelId || model.model_id === selectedModelId)?.display_name ||
    selectedModelId ||
    'Modelo'
  const activeBranchLabel = headBranch ?? activeBaseBranch ?? 'develop'
  const sandboxLabel = activeSandboxName ?? 'Sandbox'
  const hasUsageMeta =
    convUsage.total_prompt_tokens > 0 ||
    convUsage.total_completion_tokens > 0 ||
    (liveUsage ? liveUsage.prompt_tokens > 0 || liveUsage.completion_tokens > 0 : false) ||
    !!liveUsage?.fallback

  return (
    <div className={styles.activeChat}>
      {/* Session header — env + branch + diff stats + PR + painel ficheiros/diff */}
      <div className={styles.sessionHeader}>
        <div className={styles.sessionHeaderInner}>
          <div className={styles.sessionHeaderLeft}>
          {activeEnvSlug ? (
            <>
              <span className={`${styles.icon} ${styles.sessionHeaderIcon}`}>folder_open</span>
              <span className={styles.sessionHeaderEnv}>{activeEnvName ?? activeEnvSlug}</span>
              {activeBaseBranch && (
                <span className={styles.sessionHeaderBranch}>
                  <span className={`${styles.icon} ${styles.sessionHeaderBranchIcon}`}>account_tree</span>
                  <span className={styles.sessionHeaderBranchText}>seu espaço isolado</span>
                  <span className={styles.sessionHeaderBranchSep}>·</span>
                  <span className={styles.sessionHeaderBranchName}>{activeBranchLabel}</span>
                </span>
              )}
            </>
          ) : (
            <span className={styles.sessionHeaderEnv} style={{ opacity: 0.85 }}>
              Conversa (sem repositório ligado)
            </span>
          )}
          </div>
          <div className={styles.sessionHeaderRight}>
          <div className={styles.sessionPresenceChip} title="Sandbox desta conversa">
            <span className={styles.sessionPresenceAvatars}>
              <span className={styles.icon}>dns</span>
            </span>
            <span>{sandboxLabel}</span>
          </div>
          {models.length > 0 ? (
            <div className={styles.sessionHeaderModelPicker}>
              <ModelPicker
                models={models}
                value={selectedModelId}
                onChange={setSelectedModelId}
                disabled={streaming}
                compact
              />
            </div>
          ) : (
            <div className={styles.sessionModelChip} title={selectedModelLabel}>
              <span aria-hidden />
              {selectedModelLabel}
            </div>
          )}
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
                        style={{ fontSize: '0.72rem', color: 'var(--destructive)', maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
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
                <AgentBubble compact>
                  <SessionProgressCard
                    stages={sessionProgress}
                    elapsedMs={streamElapsedMs}
                    idleMs={streamIdleMs}
                  />
                </AgentBubble>
              )}
              {messages.map((m, index) => (
                <Fragment key={m.id}>
                  {sessionProgress.length > 0 && index === sessionProgressBeforeIndex && (
                    <AgentBubble compact>
                      <SessionProgressCard
                        stages={sessionProgress}
                        elapsedMs={streamElapsedMs}
                        idleMs={streamIdleMs}
                      />
                    </AgentBubble>
                  )}
                  <PaperMessage
                    key={m.id}
                    role={m.role}
                    content={m.content}
                    modelUsed={m.model_used ?? null}
                    promptTokens={m.prompt_tokens ?? 0}
                    completionTokens={m.completion_tokens ?? 0}
                    costUsd={m.cost_usd ?? 0}
                    payloadDiagnostics={m.payload_diagnostics ?? null}
                  />
                  {activityTraceFor(m)?.steps.length ? (
                    <AgentBubble compact>
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
                    </AgentBubble>
                  ) : null}
                </Fragment>
              ))}
              {((thoughtSteps.length > 0 && !sessionProgressAnchor) || (streaming && showThinking)) && (
                <AgentBubble compact>
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
                </AgentBubble>
              )}

              {pendingAction && (
                <AgentBubble compact>
                  <ActionRequiredCard action={pendingAction} onReply={onActionReply} />
                </AgentBubble>
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
          {slashOpen && (
            <div className={styles.slashCommandOverlay}>
              <SlashCommandMenu
                commands={slashCommands}
                query={slashQuery}
                onPick={pickSlashCommand}
                onDismiss={() => setSlashOpen(false)}
              />
            </div>
          )}
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
            onChange={(e) => {
              const next = e.target.value
              setInput(next)
              openSlashCommands(next, e.target.selectionStart ?? next.length)
            }}
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

          {confirmCommand && (
            <div className={styles.commandFeedback}>
              <CommandConfirmation
                message={confirmCommand.message}
                confirmLabel={confirmCommand.confirmLabel}
                cancelLabel={confirmCommand.cancelLabel}
                onCancel={() => setConfirmCommand(null)}
                onConfirm={() => void runSlashCommand(confirmCommand.command, true)}
              />
            </div>
          )}
          {commandNotice && (
            <div className={styles.commandFeedback} role="status">
              {commandNotice}
            </div>
          )}

          <div className={styles.chatContextBar}>
            <PermissionModeControl
              value={permissionMode}
              onChange={setPermissionMode}
              disabled={streaming}
              runtimeConfirmed={permissionWarningRuntimeConfirmed}
              compact
            />
            {hasUsageMeta && (
              <>
              {(convUsage.total_prompt_tokens > 0 || convUsage.total_completion_tokens > 0) && (
                <div
                  className={styles.chatContextPill}
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
                  title="Último turno (ainda não consolidado nos totais)"
                >
                  <span className={`${styles.icon} ${styles.chatContextIcon}`}>bolt</span>
                  <span className={styles.chatContextText}>
                    +{liveUsage.prompt_tokens + liveUsage.completion_tokens} tok agora
                  </span>
                </div>
              )}
              {liveUsage?.fallback && (
                <div
                  className={`${styles.chatContextPill} ${styles.chatContextPillNotice}`}
                  title={`Selecionado: ${liveUsage.fallback.selected_model} | final: ${liveUsage.fallback.final_model}`}
                >
                  <span className={`${styles.icon} ${styles.chatContextIcon}`}>swap_horiz</span>
                  <span className={styles.chatContextText}>
                    final {liveUsage.fallback.final_model}
                  </span>
                  <span className={styles.chatContextReason}>
                    {fallbackReasonLabel(liveUsage.fallback.reason)}
                  </span>
                </div>
              )}
              </>
            )}
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
function AgentBubble({
  children,
  compact = false,
}: {
  children: React.ReactNode
  compact?: boolean
}) {
  return (
    <div className={`${styles.agentBubble} ${compact ? styles.agentBubbleCompact : ''}`}>
      <div className={styles.agentBubbleAvatar}>
        <img src="/capybara.png" alt="" />
      </div>
      <div className={styles.agentBubbleBody}>{children}</div>
    </div>
  )
}

function CodeBlockCard({
  code,
  language,
}: {
  code: string
  language: string
}) {
  const [copied, setCopied] = useState(false)
  const normalizedLanguage = language.toLowerCase()
  const label = normalizedLanguage === 'sql'
    ? 'Consulta pronta · SQL'
    : `Código · ${normalizedLanguage.toUpperCase()}`

  async function handleCopy() {
    try {
      await navigator.clipboard?.writeText(code)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1400)
    } catch {
      /* clipboard pode estar bloqueado */
    }
  }

  return (
    <div className={styles.codeBlockCard}>
      <div className={styles.codeBlockHeader}>
        <span>{label}</span>
        <button type="button" onClick={handleCopy}>
          <span className={styles.icon}>{copied ? 'check' : 'content_copy'}</span>
          {copied ? 'copiado' : 'copiar'}
        </button>
      </div>
      <pre>
        <code className={`language-${normalizedLanguage}`}>
          {normalizedLanguage === 'sql' ? renderSqlTokens(code) : code}
        </code>
      </pre>
    </div>
  )
}

const SQL_KEYWORDS = new Set([
  'select', 'from', 'where', 'join', 'inner', 'left', 'right', 'full', 'outer',
  'on', 'and', 'or', 'as', 'group', 'by', 'order', 'having', 'limit', 'offset',
  'insert', 'into', 'update', 'delete', 'values', 'set', 'case', 'when', 'then',
  'else', 'end', 'distinct', 'union', 'all', 'count', 'sum', 'avg', 'min', 'max',
])

function renderSqlTokens(code: string): React.ReactNode[] {
  const tokenPattern = /(--.*? $|'(?:''|[^'])*'|:[a-zA-Z_][\w]*|\b\d+(?:\.\d+)?\b|\b[a-zA-Z_][\w]*\b)/gm
  const nodes: React.ReactNode[] = []
  let lastIndex = 0
  let tokenIndex = 0

  for (const match of code.matchAll(tokenPattern)) {
    const value = match[0]
    const index = match.index ?? 0
    if (index > lastIndex) nodes.push(code.slice(lastIndex, index))

    const lower = value.toLowerCase()
    const className = value.startsWith('--')
      ? styles.sqlComment
      : value.startsWith("'")
        ? styles.sqlString
        : value.startsWith(':')
          ? styles.sqlParam
          : /^\d/.test(value)
            ? styles.sqlNumber
            : SQL_KEYWORDS.has(lower)
              ? styles.sqlKeyword
              : undefined

    nodes.push(className ? <span className={className} key={tokenIndex}>{value}</span> : value)
    tokenIndex += 1
    lastIndex = index + value.length
  }

  if (lastIndex < code.length) nodes.push(code.slice(lastIndex))
  return nodes
}

function PaperMessage({
  role,
  content,
  streaming,
  modelUsed,
  promptTokens,
  completionTokens,
  costUsd,
  payloadDiagnostics,
}: {
  role: string
  content: string
  streaming?: boolean
  modelUsed?: string | null
  promptTokens?: number
  completionTokens?: number
  costUsd?: number
  payloadDiagnostics?: PayloadSizeBreakdown | null
}) {
  const isUser = role === 'user'
  const totalTokens = (promptTokens ?? 0) + (completionTokens ?? 0)
  const hasUsage =
    !isUser && (totalTokens > 0 || !!modelUsed)
  const costLabel = totalTokens === 0 && (costUsd ?? 0) === 0
    ? 'uso não informado'
    : formatCostUsd(costUsd ?? 0)
  const messageBubble = (
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
      {!isUser && payloadDiagnostics && (
        <PayloadDiagnosticSummary diagnostics={payloadDiagnostics} />
      )}
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

  if (isUser) return messageBubble
  return <AgentBubble>{messageBubble}</AgentBubble>
}

function PayloadDiagnosticSummary({ diagnostics }: { diagnostics: PayloadSizeBreakdown }) {
  const [expanded, setExpanded] = useState(false)
  const categories = diagnostics.categories ?? []
  const topCategories = categories.slice(0, 3)
  return (
    <div className={styles.payloadDiagnostic}>
      <button
        type="button"
        className={styles.payloadDiagnosticToggle}
        onClick={() => setExpanded((value) => !value)}
        aria-expanded={expanded}
        aria-label="Alternar detalhes do payload"
      >
        <span className={`${styles.icon} ${styles.payloadDiagnosticIcon}`} aria-hidden="true">
          data_object
        </span>
        <span className={styles.payloadDiagnosticTitle}>Pedido</span>
        <strong className={styles.payloadDiagnosticTotal}>
          {formatByteSize(diagnostics.total_size_bytes)}
        </strong>
        {topCategories.length > 0 && (
          <span className={styles.payloadDiagnosticChips}>
            {topCategories.map((category) => (
              <span className={styles.payloadDiagnosticChip} key={category.key}>
                {category.label} {formatByteSize(category.size_bytes)}
              </span>
            ))}
          </span>
        )}
        {categories.length > 0 && (
          <span className={`${styles.icon} ${styles.payloadDiagnosticChevron}`} aria-hidden="true">
            {expanded ? 'expand_less' : 'expand_more'}
          </span>
        )}
      </button>
      {expanded && categories.length > 0 && (
        <div className={styles.payloadDiagnosticDetails}>
          {categories.map((category) => (
            <div className={styles.payloadDiagnosticRow} key={category.key}>
              <span className={styles.payloadDiagnosticLabel}>{category.label}</span>
              <span className={styles.payloadDiagnosticBar} aria-hidden="true">
                <span
                  className={styles.payloadDiagnosticBarFill}
                  style={{ width: `${Math.min(100, Math.max(0, category.percentage ?? 0))}%` }}
                />
              </span>
              <span className={styles.payloadDiagnosticValue}>
                {formatByteSize(category.size_bytes)}
                {category.percentage != null ? ` · ${category.percentage.toFixed(1)}%` : ''}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function SandboxAccessView({
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

function isSandboxAvailable(sandbox: Sandbox): boolean {
  return sandbox.status === 'active' && (
    sandbox.container_status === 'running' ||
    sandbox.container_status === 'configured'
  )
}

function sandboxStatusLabel(sandbox: Sandbox): string {
  if (sandbox.status === 'offline') return 'Offline'
  if (sandbox.container_status === 'configured') return 'Configurada'
  if (sandbox.container_status === 'running') return 'Rodando'
  if (sandbox.container_status === 'starting') return 'Iniciando'
  if (sandbox.container_status === 'error') return 'Erro'
  if (sandbox.container_status === 'stopped') return 'Parada'
  if (sandbox.container_status === 'not_created') return 'Não criada'
  return sandbox.status || sandbox.container_status
}

function sandboxStatusClass(sandbox: Sandbox): string {
  if (sandbox.container_status === 'error') return styles.sandboxStatusBadgeError
  if (isSandboxAvailable(sandbox)) return styles.sandboxStatusBadgeActive
  return styles.sandboxStatusBadgeMuted
}

function formatByteSize(value: number): string {
  const bytes = Math.max(0, Math.round(value || 0))
  if (bytes < 1024) return `${bytes} B`
  const kb = bytes / 1024
  if (kb < 1024) return `${kb.toFixed(kb >= 10 ? 0 : 1)} KB`
  const mb = kb / 1024
  return `${mb.toFixed(mb >= 10 ? 0 : 1)} MB`
}
