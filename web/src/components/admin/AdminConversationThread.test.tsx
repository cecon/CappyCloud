import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { AdminConversationAttachment, AdminConversationDetail } from '../../api'
import * as api from '../../api'
import { AdminConversationThread } from './AdminConversationThread'
import { groupByMessage } from './attachmentsByMessage'

function attachment(id: string, messageId: string | null, kind = 'image'): AdminConversationAttachment {
  return {
    id,
    conversation_id: 'c1',
    message_id: messageId,
    mime_type: kind === 'image' ? 'image/png' : 'application/pdf',
    original_filename: `${id}.${kind === 'image' ? 'png' : 'pdf'}`,
    size_bytes: 10,
    kind,
    has_description: true,
    processing_status: 'described',
    chunks_count: 0,
    processing_error: null,
    vision_model_used: null,
    uploaded_at: '2026-10-26T12:00:00Z',
    preview_url: `/api/admin/conversations/c1/attachments/${id}`,
  }
}

const DETAIL: AdminConversationDetail = {
  id: 'c1',
  title: 'Erro no faturamento',
  user_email: 'alef@test.com',
  workspace_slug: 'protheus',
  workspace_name: 'PROTHEUS',
  ticket_number: null,
  created_at: '2026-10-26T12:00:00Z',
  last_message_at: null,
  questions: 1,
  message_count: 2,
  cost_usd: 0.1,
  pr_url: null,
  archived: false,
  messages: [
    { id: 'q1', role: 'user', content: 'Veja o print', created_at: '2026-10-26T12:00:00Z',
      model_used: null, prompt_tokens: 0, completion_tokens: 0, cost_usd: 0 },
    { id: 'a1', role: 'assistant', content: 'Falta o **CNAE**.', created_at: '2026-10-26T12:01:00Z',
      model_used: 'claude-sonnet-5', prompt_tokens: 100, completion_tokens: 10, cost_usd: 0.1 },
  ],
}

afterEach(() => vi.restoreAllMocks())

describe('groupByMessage', () => {
  it('agrupa por pergunta e ignora anexo sem pergunta', () => {
    const grouped = groupByMessage([attachment('a', 'q1'), attachment('b', null), attachment('c', 'q1', 'pdf')])
    expect([...grouped.keys()]).toEqual(['q1'])
    expect(grouped.get('q1')?.map((a) => a.id)).toEqual(['a', 'c'])
  })
})

describe('AdminConversationThread', () => {
  it('mostra as mensagens como no chat, com anexos e passos do agente', async () => {
    vi.spyOn(api, 'fetchAdminConversationActivity').mockResolvedValue([
      {
        task_id: 't1',
        user_message_id: 'q1',
        status: 'done',
        model_used: 'claude-sonnet-5',
        created_at: '2026-10-26T12:00:01Z',
        completed_at: '2026-10-26T12:00:30Z',
        last_event_at: '2026-10-26T12:00:30Z',
        events: [
          { type: 'tool_start', data: { name: 'Grep', id: 'u1', input: '{"pattern":"CNAE"}' }, at: '2026-10-26T12:00:02Z' },
          { type: 'tool_result', data: { id: 'u1', output: 'ok' }, at: '2026-10-26T12:00:03Z' },
          { type: 'done', data: {}, at: '2026-10-26T12:00:30Z' },
        ],
      },
    ])
    vi.spyOn(api, 'fetchAdminConversationAttachments').mockResolvedValue([
      attachment('print', 'q1'),
      attachment('manual', 'q1', 'pdf'),
    ])
    const blob = vi.spyOn(api, 'fetchAdminAttachmentBlobUrl').mockResolvedValue('blob:print')

    render(<AdminConversationThread detail={DETAIL} token="tok" />)

    expect(screen.getByText('Veja o print')).toBeInTheDocument()
    expect(screen.getByText('alef@test.com')).toBeInTheDocument()
    expect(screen.getByText('CNAE')).toBeInTheDocument()
    expect(await screen.findByText('manual.pdf')).toBeInTheDocument()
    expect(await screen.findByAltText('print.png')).toHaveAttribute('src', 'blob:print')
    expect(blob).toHaveBeenCalledWith('tok', 'c1', 'print')
    expect(await screen.findByText(/^Pensei por/)).toBeInTheDocument()
  })

  it('continua mostrando as mensagens quando passos e anexos falham', async () => {
    vi.spyOn(api, 'fetchAdminConversationActivity').mockRejectedValue(new Error('x'))
    vi.spyOn(api, 'fetchAdminConversationAttachments').mockRejectedValue(new Error('x'))

    render(<AdminConversationThread detail={DETAIL} token="tok" />)

    expect(await screen.findByText(/Não foi possível carregar os passos/)).toBeInTheDocument()
    expect(screen.getByText('Veja o print')).toBeInTheDocument()
  })
})
