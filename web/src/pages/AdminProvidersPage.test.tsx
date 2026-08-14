import { render, screen } from '@testing-library/react'
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
})
