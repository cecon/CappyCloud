import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { setToken } from '../api'
import { AdminProvidersPage } from './AdminProvidersPage'

describe('AdminProvidersPage', () => {
  beforeEach(() => {
    setToken('token')
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    setToken(null)
  })

  it('renders administrator-only provider auth state without exposing secrets', async () => {
    vi.stubGlobal('fetch', vi.fn(async (url: RequestInfo | URL) => {
      const path = String(url)
      if (path.endsWith('/api/auth/me')) {
        return new Response(JSON.stringify({
          id: 'user-1',
          email: 'admin@example.com',
          role: 'admin',
          is_super_admin: true,
          must_change_password: false,
        }))
      }
      if (path.endsWith('/api/admin/providers')) {
        return new Response(JSON.stringify([
          {
            id: 'provider-1',
            name: 'Azure',
            base_url: 'https://azure.example/openai/v1',
            api_format: 'responses',
            active: true,
            last_synced_at: null,
            models_count: 2,
            auth_state: 'missing-key',
            auth_label: 'Chave pendente',
            auth_next_action: 'Cadastre a chave do provider para liberar execução no runtime.',
          },
        ]))
      }
      return new Response('{}', { status: 404 })
    }))

    render(<AdminProvidersPage />)

    expect(await screen.findByText('Azure')).toBeInTheDocument()
    expect(screen.getByText('Chave pendente')).toBeInTheDocument()
    expect(screen.getByText(/Cadastre a chave do provider/i)).toBeInTheDocument()
    expect(screen.queryByText(/sk-/i)).not.toBeInTheDocument()
  })

  it('adds a manual model to an existing provider', async () => {
    const calls: Array<{ path: string; method: string; body: unknown }> = []
    vi.stubGlobal('fetch', vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
      const path = String(url)
      calls.push({
        path,
        method: init?.method ?? 'GET',
        body: init?.body ? JSON.parse(String(init.body)) : null,
      })
      if (path.endsWith('/api/auth/me')) {
        return new Response(JSON.stringify({
          id: 'user-1',
          email: 'admin@example.com',
          role: 'admin',
          is_super_admin: true,
          must_change_password: false,
        }))
      }
      if (path.endsWith('/api/admin/providers')) {
        return new Response(JSON.stringify([
          {
            id: 'provider-1',
            name: 'Azure',
            base_url: 'https://azure.example/openai/v1',
            api_format: 'responses',
            active: true,
            last_synced_at: null,
            models_count: 1,
            auth_state: 'configured',
            auth_label: 'Chave configurada',
            auth_next_action: '',
          },
        ]))
      }
      if (path.endsWith('/api/admin/providers/provider-1/models')) {
        return new Response(JSON.stringify({ id: 'model-1' }), { status: 201 })
      }
      return new Response('{}', { status: 404 })
    }))

    render(<AdminProvidersPage />)

    await screen.findByText('Azure')
    const addButton = await screen.findByRole('button', { name: 'Adicionar modelo' })
    await waitFor(() => expect(addButton).not.toBeDisabled())
    fireEvent.click(addButton)
    fireEvent.change(await screen.findByPlaceholderText('claude-opus-5-5'), {
      target: { value: ' claude-opus-5-5 ' },
    })
    fireEvent.change(screen.getByPlaceholderText('Claude Opus 5.5'), {
      target: { value: 'Claude Opus 5.5' },
    })
    fireEvent.click(screen.getByLabelText('Lê imagem (visão)'))
    fireEvent.click(screen.getByRole('button', { name: 'Salvar' }))

    await waitFor(() => {
      expect(calls).toContainEqual({
        path: expect.stringContaining('/api/admin/providers/provider-1/models'),
        method: 'POST',
        body: {
          model_id: 'claude-opus-5-5',
          display_name: 'Claude Opus 5.5',
          capabilities: ['text', 'vision'],
        },
      })
    })
  })
})
