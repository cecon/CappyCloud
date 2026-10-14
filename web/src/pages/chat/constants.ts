import type { StreamToolStats } from './types'

export const ALLOWED_ATTACHMENT_MIME = new Set([
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
export const ALLOWED_ATTACHMENT_EXT = new Set([
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
export const MAX_IMAGE_ATTACHMENT_BYTES = 8 * 1024 * 1024
export const MAX_ARTIFACT_ATTACHMENT_BYTES = 50 * 1024 * 1024
export const IMAGE_ONLY_PROMPT =
  'Analise a imagem anexada, descreva o erro visível e indique os próximos passos.'

export const STICKY_SCROLL_THRESHOLD_PX = 96
export const CHAT_PREFS_KEY = 'cappycloud.chat.preferences.v1'
export const CHAT_CONVERSATIONS_COLLAPSED_KEY = 'cappycloud.chat.conversationsCollapsed'
export const CONVERSATION_PAGE_SIZE = 6
export const HEAVY_TURN_TOOL_THRESHOLD = 40
export const HEAVY_TURN_PROMPT_TOKEN_THRESHOLD = 200_000
export const HEAVY_TURN_COST_THRESHOLD_USD = 1

export const EMPTY_STREAM_TOOL_STATS: StreamToolStats = { total: 0, broadSearches: 0 }

export const LAST_WORKSPACE_KEY = 'cappy.lastWorkspaceId'
export const CLAUDE_CLI_MODEL_KEY = 'cappy.claudeCliModel'
