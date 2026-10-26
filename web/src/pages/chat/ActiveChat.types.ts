import type {
  ActionRequiredEvent,
  AiModel,
  ChatMessage,
  ContextProgressEvent,
  ConversationUsage,
  DoneEvent,
  ExecutionProfile,
  PermissionMode,
  RuntimeStateEvent,
} from '../../api'
import type { TrayItem, TrayNotice } from '../../components/AttachmentTray'
import type { ThoughtStep } from '../../components/ThinkingStream'
import type { TimedSubagentGroup } from '../../components/chat/subagentGroups'
import type { ActivityTrace, PrLink, SessionProgressAnchor, StreamToolStats } from './types'

/* ────────────────────────────────────────────────────────────────
   Active Chat — mensagens + input compacto
   ──────────────────────────────────────────────────────────────── */
export interface ActiveChatProps {
  messages: ChatMessage[]
  messagesLoading: boolean
  messagesError: string | null
  sessionProgressAnchor: SessionProgressAnchor | null
  thoughtSteps: ThoughtStep[]
  activityTraces: Record<string, ActivityTrace>
  streamElapsedMs: number
  /** Relógio da resposta em andamento (início + decorrido), para os tempos dos cartões. */
  streamNowMs: number
  streamIdleMs: number
  pendingAction: ActionRequiredEvent | null
  contextProgress: ContextProgressEvent | null
  subagentGroups: TimedSubagentGroup[]
  runtimeStates: RuntimeStateEvent[]
  streamToolStats: StreamToolStats
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
  prLinks: PrLink[]
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
  planModeEnabled: boolean
  executionProfile: ExecutionProfile
  setExecutionProfile: (profile: ExecutionProfile) => void
  permissionWarningRuntimeConfirmed: boolean
  convUsage: ConversationUsage
  liveUsage: DoneEvent | null
  // Anexos
  trayItems: TrayItem[]
  onPickFiles: (files: FileList | null | undefined) => void
  onPasteFiles: (e: React.ClipboardEvent<HTMLTextAreaElement>) => void
  onRemoveTrayItem: (localId: string) => void
  trayNotice: TrayNotice | null
  fileInputRef: React.RefObject<HTMLInputElement | null>
  isDragOver: boolean
  setDragOver: (v: boolean) => void
}
