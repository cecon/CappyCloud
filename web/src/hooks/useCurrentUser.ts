import { useEffect, useState } from 'react'
import { type CurrentUser, fetchCurrentUser, getToken } from '../api'

type State =
  | { status: 'loading' }
  | { status: 'ready'; user: CurrentUser }
  | { status: 'anonymous' }
  | { status: 'error'; message: string }

/**
 * Resolve o utilizador autenticado uma única vez por load. Não revalida em
 * cada render — para PR2 a UI assume que o role muda apenas em logout/login
 * (ADR-005 não exige refresh ao vivo).
 */
export function useCurrentUser(): State {
  const [state, setState] = useState<State>(() => {
    return getToken() ? { status: 'loading' } : { status: 'anonymous' }
  })

  useEffect(() => {
    const token = getToken()
    if (!token) return
    let cancelled = false
    fetchCurrentUser(token)
      .then((user) => {
        if (!cancelled) setState({ status: 'ready', user })
      })
      .catch((err: unknown) => {
        if (cancelled) return
        const message = err instanceof Error ? err.message : 'Falha ao carregar utilizador'
        setState({ status: 'error', message })
      })
    return () => {
      cancelled = true
    }
  }, [])

  return state
}
