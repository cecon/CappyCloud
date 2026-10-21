import type { ExecutionProfile, PermissionMode } from '../../api'
import type { ThoughtStep } from '../../components/ThinkingStream'

export type PrLink = { label: string; url: string }

export type ChatMainMode = 'chat' | 'sandboxes'

export type StreamToolStats = {
  total: number
  broadSearches: number
}

export type PermissionModeOption = {
  value: PermissionMode
  label: string
  icon: string
  description: string
  tone?: 'safe' | 'warn' | 'danger'
}

export type ExecutionProfileOption = {
  value: ExecutionProfile
  label: string
  icon: string
  description: string
  searchBudget: string
}

export type RepoChatPreference = {
  branch?: string
  modelId?: string
}

export type ChatPreferenceState = {
  lastRepoSlug?: string
  lastModelId?: string
  executionProfile?: ExecutionProfile
  byRepo?: Record<string, RepoChatPreference>
}

export type SessionProgressAnchor = {
  id: string
  content: string
}

export type ActivityTrace = {
  content: string
  steps: ThoughtStep[]
  elapsedMs: number
  interrupted?: boolean
}
