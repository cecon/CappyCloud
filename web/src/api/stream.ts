import { apiFetch } from './http'
import type { ExecutionProfile, PermissionMode } from './preferences'
import { parseContextProgress, parseFallbackNotice, parsePayloadDiagnostics, parseRuntimeState, parseStatusEvent, parseSubagentGroup } from './streamParsers'
import type { StreamHandlers } from './streamTypes'

/**
 * Envia mensagem e processa o stream SSE JSON com handlers tipados.
 * O backend envia eventos no formato: data: {"type":"...","..."}\n\n
 */
export async function streamAssistantReply(
  token: string,
  conversationId: string,
  content: string,
  handlers: StreamHandlers,
  modelId?: string | null,
  attachmentIds?: string[] | null,
  permissionMode?: PermissionMode | null,
  executionProfile?: ExecutionProfile | null,
  cursor?: number | null,
  actionReply = false,
): Promise<void> {
  const { signal, ...eventHandlers } = handlers
  const bodyPayload: Record<string, unknown> = { content }
  if (modelId) bodyPayload.model_id = modelId
  if (attachmentIds && attachmentIds.length > 0) bodyPayload.attachment_ids = attachmentIds
  if (permissionMode) bodyPayload.permission_mode = permissionMode
  if (executionProfile) bodyPayload.execution_profile = executionProfile
  if (actionReply) bodyPayload.action_reply = true
  let retryCursor = cursor
  let retries = 0
  let reader: ReadableStreamDefaultReader<Uint8Array>

  async function openReader(): Promise<ReadableStreamDefaultReader<Uint8Array>> {
    const qs = retryCursor != null ? `?cursor=${encodeURIComponent(String(retryCursor))}` : ''
    const res = await apiFetch(`/api/conversations/${conversationId}/messages/stream${qs}`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(bodyPayload),
      signal,
    })
    if (!res.ok) {
      const err = await res.text()
      throw new Error(err || 'Erro no agente')
    }
    return res.body!.getReader()
  }
  reader = await openReader()
  const dec = new TextDecoder()
  let buf = ''
  let accText = ''
  let sawDone = false
  let lastCursor = cursor

  while (!sawDone) {
    let chunk: ReadableStreamReadResult<Uint8Array>
    try {
      chunk = await reader.read()
    } catch (e) {
      if (e instanceof Error && e.name === 'AbortError') throw e
      if (lastCursor == null || retries >= 3) throw e
      retries += 1
      retryCursor = lastCursor
      await new Promise((resolve) => setTimeout(resolve, 400 * retries))
      reader = await openReader()
      continue
    }
    const { done, value } = chunk
    if (done) {
      if (!sawDone && lastCursor != null && retries < 3) {
        retries += 1
        retryCursor = lastCursor
        await new Promise((resolve) => setTimeout(resolve, 400 * retries))
        reader = await openReader()
        continue
      }
      break
    }
    retries = 0
    buf += dec.decode(value, { stream: true })

    // Process all complete SSE lines; keep any partial line in buf
    const lines = buf.split('\n')
    buf = lines.pop() ?? ''

    for (const line of lines) {
      if (!line.startsWith('data: ')) continue
      try {
        const evt = JSON.parse(line.slice(6)) as Record<string, unknown>
        if (typeof evt.cursor === 'number') {
          lastCursor = evt.cursor
          eventHandlers.onCursor?.(evt.cursor)
        }
        switch (evt.type) {
          case 'text':
            accText += (evt.content as string) ?? ''
            eventHandlers.onText(accText)
            break
          case 'tool_start':
            eventHandlers.onToolStart({
              name: evt.name as string,
              input: (evt.input as string) ?? '',
              id: evt.id as string,
            })
            break
          case 'tool_result':
            eventHandlers.onToolResult({
              name: evt.name as string,
              output: (evt.output as string) ?? '',
              is_error: (evt.is_error as boolean) ?? false,
              id: evt.id as string,
            })
            break
          case 'command_start':
            eventHandlers.onCommandStart?.({
              command: (evt.command as string) ?? '',
              label: (evt.label as string) ?? 'Comando iniciado',
            })
            break
          case 'command_result': {
            const status = evt.status
            eventHandlers.onCommandResult?.({
              command: (evt.command as string) ?? '',
              status:
                status === 'started' ||
                status === 'waiting_for_input' ||
                status === 'completed' ||
                status === 'unavailable' ||
                status === 'failed' ||
                status === 'cancelled'
                  ? status
                  : 'failed',
              summary: (evt.summary as string) ?? 'Comando finalizado.',
              details_markdown: (evt.details_markdown as string | null) ?? null,
            })
            break
          }
          case 'action_required':
            eventHandlers.onActionRequired({
              prompt_id: evt.prompt_id as string,
              question: evt.question as string,
              action_type: (evt.action_type as number) ?? 0,
              choices: (evt.choices as string[] | null) ?? null,
            })
            break
          case 'status':
            eventHandlers.onStatus(parseStatusEvent(evt))
            break
          case 'payload_diagnostic': {
            const diagnostics = parsePayloadDiagnostics(evt.diagnostics)
            if (diagnostics) {
              eventHandlers.onPayloadDiagnostic?.(diagnostics)
            }
            break
          }
          case 'context_progress':
            eventHandlers.onContextProgress?.(parseContextProgress(evt))
            break
          case 'subagent_group':
            eventHandlers.onSubagentGroup?.(parseSubagentGroup(evt))
            break
          case 'permission_timeout':
            eventHandlers.onRuntimeState?.(parseRuntimeState(evt, 'permission-timeout'))
            break
          case 'stalled':
            eventHandlers.onRuntimeState?.(parseRuntimeState(evt, 'stalled'))
            break
          case 'canceled':
            eventHandlers.onRuntimeState?.(parseRuntimeState(evt, 'canceled'))
            break
          case 'error':
            eventHandlers.onRuntimeState?.(parseRuntimeState(evt, 'failed'))
            eventHandlers.onError((evt.message as string) ?? 'Erro desconhecido')
            break
          case 'done':
            eventHandlers.onDone?.({
              model_used: (evt.model_used as string | null) ?? null,
              prompt_tokens: (evt.prompt_tokens as number) ?? 0,
              completion_tokens: (evt.completion_tokens as number) ?? 0,
              fallback: parseFallbackNotice(evt.fallback),
            })
            eventHandlers.onRuntimeState?.(parseRuntimeState(evt, 'done'))
            sawDone = true
            break
        }
      } catch {
        // Ignore malformed SSE lines
      }
    }
  }
  if (sawDone) {
    reader.cancel().catch(() => {
      // Stream already closed.
    })
  }
}
