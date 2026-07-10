import type { ReactNode } from 'react'
import { Navigate } from 'react-router-dom'
import { Center, Loader, Stack, Text } from '@/components/ui/legacy'
import { useCurrentUser } from '../hooks/useCurrentUser'

type Props = {
  children: ReactNode
}

export function RequireSuperAdmin({ children }: Props) {
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

  if (!state.user.is_super_admin) {
    return <Navigate to="/" replace />
  }

  return <>{children}</>
}
