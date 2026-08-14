import { describe, expect, it, vi } from 'vitest'

import { streamAssistantReply, updateGitProviderToken, type StreamHandlers } from './api'

function streamFromEvents(events: Array<Record<string, unknown>>): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder()
  return new ReadableStream({
    start(controller) {
      for (const event of events) {
        controller.enqueue(encoder.encode(`data: ${JSON.stringify(event)}\n\n`))
      }
      controller.close()
    },
  })
}

function handlers(overrides: Partial<StreamHandlers> = {}): StreamHandlers {
  return {
    onText: vi.fn(),
    onToolStart: vi.fn(),
    onToolResult: vi.fn(),
    onActionRequired: vi.fn(),
    onStatus: vi.fn(),
    onError: vi.fn(),
    ...overrides,
  }
}

describe('streamAssistantReply', () => {
  it('sends execution profile without changing the selected model', async () => {
    const fetchMock = vi.fn(async () => new Response(streamFromEvents([{ type: 'done' }])))
    vi.stubGlobal('fetch', fetchMock)

    await streamAssistantReply(
      'token',
      'conversation',
      'oi',
      handlers(),
      'openai/gpt-5.5',
      null,
      'bypass_permissions',
      'fast',
    )

    const [, init] = fetchMock.mock.calls[0] as unknown as [RequestInfo | URL, RequestInit]
    expect(JSON.parse(String(init?.body))).toMatchObject({
      content: 'oi',
      model_id: 'openai/gpt-5.5',
      permission_mode: 'bypass_permissions',
      execution_profile: 'fast',
    })
  })

  it('parses context progress without treating it as cost', async () => {
    const onContextProgress = vi.fn()
    vi.stubGlobal('fetch', vi.fn(async () => new Response(streamFromEvents([
      {
        type: 'context_progress',
        label: 'Contexto usado',
        current_value: 12,
        limit_value: 100,
        percent: 12,
        financial: true,
      },
      { type: 'done' },
    ]))))

    await streamAssistantReply('token', 'conversation', 'oi', handlers({ onContextProgress }))

    expect(onContextProgress).toHaveBeenCalledWith({
      label: 'Contexto usado',
      current_value: 12,
      limit_value: 100,
      percent: 12,
      financial: false,
    })
  })

  it('parses grouped subagent activity as collapsible parent-turn data', async () => {
    const onSubagentGroup = vi.fn()
    vi.stubGlobal('fetch', vi.fn(async () => new Response(streamFromEvents([
      {
        type: 'subagent_group',
        parent_turn_id: 'turn_1',
        label: 'Investigacoes auxiliares',
        collapsible: true,
        activities: [
          { id: 'agent_1', name: 'repo-a', state: 'done', detail: 'ok' },
          { id: 'agent_2', name: 'repo-b', state: 'unexpected', detail: 'rodando' },
        ],
      },
      { type: 'done' },
    ]))))

    await streamAssistantReply('token', 'conversation', 'oi', handlers({ onSubagentGroup }))

    expect(onSubagentGroup).toHaveBeenCalledWith({
      parent_turn_id: 'turn_1',
      label: 'Investigacoes auxiliares',
      collapsible: true,
      activities: [
        { id: 'agent_1', name: 'repo-a', state: 'done', detail: 'ok' },
        { id: 'agent_2', name: 'repo-b', state: 'tool-running', detail: 'rodando' },
      ],
    })
  })

  it('normalizes runtime state notices', async () => {
    const onRuntimeState = vi.fn()
    vi.stubGlobal('fetch', vi.fn(async () => new Response(streamFromEvents([
      { type: 'permission_timeout', message: 'sem resposta do aprovador' },
      { type: 'stalled', detail: 'sem chunks novos' },
      { type: 'canceled', label: 'Cancelado pelo usuário' },
      { type: 'done' },
    ]))))

    await streamAssistantReply('token', 'conversation', 'oi', handlers({ onRuntimeState }))

    expect(onRuntimeState).toHaveBeenCalledWith({
      state: 'permission-timeout',
      label: 'Permissão expirou',
      detail: 'sem resposta do aprovador',
      terminal: true,
    })
    expect(onRuntimeState).toHaveBeenCalledWith({
      state: 'stalled',
      label: 'Execução sem novos eventos',
      detail: 'sem chunks novos',
      terminal: false,
    })
    expect(onRuntimeState).toHaveBeenCalledWith({
      state: 'canceled',
      label: 'Cancelado pelo usuário',
      detail: '',
      terminal: true,
    })
    expect(onRuntimeState).toHaveBeenLastCalledWith({
      state: 'done',
      label: 'Execução concluída',
      detail: '',
      terminal: true,
    })
  })
})

describe('updateGitProviderToken', () => {
  it('sends provider tokens in the request body instead of the URL', async () => {
    const fetchMock = vi.fn(
      async (_input: RequestInfo | URL, _init?: RequestInit) =>
        new Response(JSON.stringify({ id: 'provider-1' })),
    )
    vi.stubGlobal('fetch', fetchMock)

    await updateGitProviderToken('jwt-token', 'provider-1', 'ghp_secret-value')

    const [url, init] = fetchMock.mock.calls[0]
    expect(String(url)).toContain('/api/git-providers/provider-1/token')
    expect(String(url)).not.toContain('ghp_secret-value')
    expect(init).toMatchObject({
      method: 'PATCH',
      body: JSON.stringify({ token: 'ghp_secret-value' }),
    })
  })
})
