import type { ChatMessage, Conversation } from './conversationTypes'
import { apiFetch, formatApiErrorPayload } from './http'
import type { RepoSelection } from './preferences'
import type { ConversationActivityTurn } from './streamTypes'

/** Renomeia e/ou arquiva a conversa (`archived: false` desarquiva). Só o dono. */
export async function updateConversation(
  token: string,
  conversationId: string,
  patch: { title?: string; archived?: boolean; ticket_number?: string },
): Promise<Conversation> {
  const res = await apiFetch(`/api/conversations/${conversationId}`, {
    method: 'PATCH',
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(patch),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || 'Não foi possível atualizar a conversa')
  }
  return res.json()
}

export async function fetchConversations(
  token: string,
  options: { scope?: 'own' | 'all'; archived?: boolean } = {},
): Promise<Conversation[]> {
  const params = new URLSearchParams()
  if (options.scope) params.set('scope', options.scope)
  if (options.archived) params.set('archived', 'true')
  const suffix = params.toString() ? `?${params.toString()}` : ''
  const res = await apiFetch(`/api/conversations${suffix}`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) throw new Error('Não foi possível carregar conversas')
  return res.json()
}

export async function createConversation(
  token: string,
  repos: RepoSelection[] = [],
  modelId?: string | null,
  sandboxId?: string | null,
  workspaceId?: string | null,
  ticketNumber?: string | null,
): Promise<Conversation> {
  const body: Record<string, unknown> = { repos }
  if (ticketNumber) body.ticket_number = ticketNumber
  if (modelId) body.model_id = modelId
  if (sandboxId) body.sandbox_id = sandboxId
  if (workspaceId) body.workspace_id = workspaceId
  const res = await apiFetch('/api/conversations', {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || 'Não foi possível criar conversa')
  }
  return res.json()
}

export async function fetchMessages(token: string, conversationId: string): Promise<ChatMessage[]> {
  const res = await apiFetch(`/api/conversations/${conversationId}/messages`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) throw new Error('Não foi possível carregar mensagens')
  return res.json()
}

/** Histórico de ações do agente por turno, para reconstruir a timeline. */
export async function fetchConversationActivity(
  token: string,
  conversationId: string,
): Promise<ConversationActivityTurn[]> {
  const res = await apiFetch(`/api/conversations/${conversationId}/activity`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) throw new Error('Não foi possível carregar o histórico de ações')
  return res.json()
}

export type SlashCommandArgument = {
  name: string
  label: string
  required: boolean
  value_hint: string
  allowed_values: string[]
  sensitive: boolean
}

export type SlashCommandAvailability = {
  state: 'available' | 'needs_arguments' | 'needs_confirmation' | 'blocked' | 'unavailable'
  reason?: string | null
  required_role?: string | null
  required_capability?: string | null
}

export type SlashCommand = {
  name: string
  description: string
  source: 'upstream' | 'cappycloud' | 'runtime' | string
  category: string
  arguments: SlashCommandArgument[]
  availability: SlashCommandAvailability
  requires_confirmation: boolean
  confirmation_reason?: string | null
  execution_mode: 'chat_action' | 'runtime_command' | 'unavailable' | string
}

export type SlashCommandCatalog = {
  runtime_version: string
  runtime_commit: string
  generated_at: string
  commands: SlashCommand[]
}

export type SlashCommandExecutionResponse = {
  status: 'needs_confirmation' | 'accepted' | 'unavailable' | 'failed' | 'completed'
  message?: string | null
  confirmation?: {
    message: string
    confirm_label: string
    cancel_label: string
  } | null
  stream?: {
    conversation_id: string
    client_request_id: string
  } | null
}

export async function listSlashCommands(
  token: string,
  conversationId: string,
): Promise<SlashCommandCatalog> {
  const res = await apiFetch(`/api/conversations/${conversationId}/commands`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) throw new Error('Nao foi possivel carregar comandos')
  return res.json()
}

export async function executeSlashCommand(
  token: string,
  conversationId: string,
  payload: {
    command: string
    arguments?: Record<string, unknown>
    confirmed?: boolean
    client_request_id: string
  },
): Promise<SlashCommandExecutionResponse> {
  const res = await apiFetch(`/api/conversations/${conversationId}/commands/execute`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      command: payload.command,
      arguments: payload.arguments ?? {},
      confirmed: payload.confirmed ?? false,
      client_request_id: payload.client_request_id,
    }),
  })
  if (!res.ok) throw new Error((await res.text()) || 'Nao foi possivel executar comando')
  return res.json()
}
