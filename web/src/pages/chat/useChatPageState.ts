import { useRef, useState } from 'react'
import {
  DEFAULT_EXECUTION_PROFILE,
  DEFAULT_PERMISSION_MODE,
  type AccessibleWorkspace,
  type ActionRequiredEvent,
  type AiModel,
  type ChatMessage,
  type ContextProgressEvent,
  type Conversation,
  type ConversationUsage,
  type DoneEvent,
  type ExecutionProfile,
  type PermissionMode,
  type RuntimeStateEvent,
  type Sandbox,
  type Workspace,
} from '../../api'
import type { ThoughtStep } from '../../components/ThinkingStream'
import type { TimedSubagentGroup } from '../../components/chat/subagentGroups'
import { CONVERSATION_PAGE_SIZE, EMPTY_STREAM_TOOL_STATS } from './constants'
import { readChatPrefs } from './preferences'
import type {
  ActivityTrace,
  ChatMainMode,
  ChatPreferenceState,
  PrLink,
  SessionProgressAnchor,
  StreamToolStats,
} from './types'

/** Estado bruto da tela de chat (conversas, catálogo, streaming, PR e refs). */
export function useChatPageState() {
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [activeId, setActiveId] = useState<string | null>(null)
  const [archivedRefreshKey, setArchivedRefreshKey] = useState(0)
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
  const [chosenPermissionMode, setPermissionModeState] = useState<PermissionMode>(DEFAULT_PERMISSION_MODE)
  const [permissionWarningRuntimeConfirmed, setPermissionWarningRuntimeConfirmed] = useState(false)
  const [executionProfile, setExecutionProfileState] = useState<ExecutionProfile>(DEFAULT_EXECUTION_PROFILE)

  const [workspaces, setWorkspaces] = useState<Workspace[]>([])
  const [sandboxes, setSandboxes] = useState<Sandbox[]>([])
  const [selectedSandboxId, setSelectedSandboxId] = useState<string>('')
  const [selectedSlug, setSelectedSlug] = useState<string>('')
  // Workspaces (pasta com vários repos) — `workspaces` acima é o catálogo de repositórios.
  const [projectWorkspaces, setProjectWorkspaces] = useState<AccessibleWorkspace[]>([])
  const [selectedWorkspaceId, setSelectedWorkspaceId] = useState<string>('')
  const [ticketNumber, setTicketNumber] = useState('')
  const [newChatError, setNewChatError] = useState<string | null>(null)
  const [selectedBranch, setSelectedBranch] = useState<string>('')
  const [models, setModels] = useState<AiModel[]>([])
  const [selectedModelId, setSelectedModelId] = useState<string>('')
  const [convUsage, setConvUsage] = useState<ConversationUsage>({
    total_prompt_tokens: 0,
    total_completion_tokens: 0,
    total_cost_usd: 0,
  })
  const [liveUsage, setLiveUsage] = useState<DoneEvent | null>(null)

  const [thoughtSteps, setThoughtSteps] = useState<ThoughtStep[]>([])
  const [streamStartedAt, setStreamStartedAt] = useState<number | null>(null)
  const [streamActivityAt, setStreamActivityAt] = useState<number | null>(null)
  const [streamElapsedMs, setStreamElapsedMs] = useState(0)
  const [pendingAction, setPendingAction] = useState<ActionRequiredEvent | null>(null)
  const [sessionProgressAnchor, setSessionProgressAnchor] = useState<SessionProgressAnchor | null>(null)
  const [contextProgress, setContextProgress] = useState<ContextProgressEvent | null>(null)
  const [subagentGroups, setSubagentGroups] = useState<TimedSubagentGroup[]>([])
  const [runtimeStates, setRuntimeStates] = useState<RuntimeStateEvent[]>([])
  const [streamToolStats, setStreamToolStats] = useState<StreamToolStats>(EMPTY_STREAM_TOOL_STATS)
  const [activityTraces, setActivityTraces] = useState<Record<string, ActivityTrace>>({})
  const [conversationsCollapsed, setConversationsCollapsed] = useState(false)

  const [diffStats, setDiffStats] = useState<{ added: number; removed: number } | null>(null)
  const [prLoading, setPrLoading] = useState(false)
  const [prLinks, setPrLinks] = useState<PrLink[]>([])
  const [prError, setPrError] = useState<string | null>(null)
  const [headBranch, setHeadBranch] = useState<string | null>(null)

  const abortControllerRef = useRef<AbortController | null>(null)
  const stopRequestedRef = useRef(false)
  const optimisticConversationIdRef = useRef<string | null>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const ticketRef = useRef<HTMLInputElement>(null)
  const chatPrefsRef = useRef<ChatPreferenceState>(readChatPrefs())
  /** Comprimento do `accumulated` text ja aplicado na timeline thoughtSteps. */
  const lastTextOffsetRef = useRef(0)
  const lastStreamCursorRef = useRef<number | null>(null)

  return {
    conversations, setConversations, activeId, setActiveId, archivedRefreshKey, setArchivedRefreshKey,
    mainMode, setMainMode, conversationSearch, setConversationSearch,
    visibleConversationCount, setVisibleConversationCount, messages, setMessages,
    messagesLoading, setMessagesLoading, messagesError, setMessagesError, input, setInput,
    streaming, setStreaming, loading, setLoading, userDefaultPermissionMode, setUserDefaultPermissionMode,
    chosenPermissionMode, setPermissionModeState,
    permissionWarningRuntimeConfirmed, setPermissionWarningRuntimeConfirmed,
    executionProfile, setExecutionProfileState,
    workspaces, setWorkspaces, sandboxes, setSandboxes, selectedSandboxId, setSelectedSandboxId,
    selectedSlug, setSelectedSlug, projectWorkspaces, setProjectWorkspaces,
    selectedWorkspaceId, setSelectedWorkspaceId, ticketNumber, setTicketNumber,
    newChatError, setNewChatError, selectedBranch, setSelectedBranch, models, setModels,
    selectedModelId, setSelectedModelId, convUsage, setConvUsage, liveUsage, setLiveUsage,
    thoughtSteps, setThoughtSteps, streamStartedAt, setStreamStartedAt,
    streamActivityAt, setStreamActivityAt, streamElapsedMs, setStreamElapsedMs,
    pendingAction, setPendingAction, sessionProgressAnchor, setSessionProgressAnchor,
    contextProgress, setContextProgress, subagentGroups, setSubagentGroups,
    runtimeStates, setRuntimeStates, streamToolStats, setStreamToolStats,
    activityTraces, setActivityTraces, conversationsCollapsed, setConversationsCollapsed,
    diffStats, setDiffStats, prLoading, setPrLoading, prLinks, setPrLinks, prError, setPrError,
    headBranch, setHeadBranch,
    abortControllerRef, stopRequestedRef, optimisticConversationIdRef, inputRef, ticketRef,
    chatPrefsRef, lastTextOffsetRef, lastStreamCursorRef,
  }
}

export type ChatPageState = ReturnType<typeof useChatPageState>
