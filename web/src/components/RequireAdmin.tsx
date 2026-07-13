import type { ReactNode } from 'react'
import { Navigate } from 'react-router-dom'
import { Center, Loader, Stack, Text } from '@/components/ui/legacy'
import { useCurrentUser } from '../hooks/useCurrentUser'

type Props = {
  children: ReactNode
}

/**
 * Wrapper de rota que exige papel ADMIN. Não-admins são redirecionados para
 * `/` (dashboard); anônimos para `/login`. Defesa em profundidade: a API já
 * retorna 403, mas evitamos que USER veja sequer o esqueleto da página.
 */
export function RequireAdmin({ children }: Props) {
  const state = useCurrentUser()

  if (state.status === 'loading') {
    return (
      <Center mih="60vh">
        <Stack gap="xs" align="center">
          <Loader />
          <Text c="dimmed" size="sm">
            Verificando permissões...
          </Text>
        </Stack>
      </Center>
    )
  }

  if (state.status === 'anonymous') {
    return <Navigate to="/login" replace />
  }

  if (state.status === 'error') {
    return (
      <Center mih="60vh">
        <Stack gap="xs" align="center">
          <Text c="red">Falha ao verificar permissão: {state.message}</Text>
        </Stack>
      </Center>
    )
  }

  if (state.user.role !== 'admin') {
    return <Navigate to="/" replace />
  }

  return <>{children}</>
}
