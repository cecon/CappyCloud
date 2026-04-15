import { useEffect, useState } from 'react'
import { Alert, Loader, Text } from '@mantine/core'
import type { EnvStatus } from '../api'

interface Props {
  status: EnvStatus
}

const messages: Record<Exclude<EnvStatus, 'running'>, string> = {
  none: 'Preparando seu ambiente...',
  stopped: 'Retomando ambiente...',
  starting: 'Iniciando ambiente...',
}

/**
 * Displays a dismissible status banner while the user's sandbox environment
 * is not yet running. Disappears automatically once status becomes 'running'.
 */
export function EnvStatusBanner({ status }: Props) {
  const [visible, setVisible] = useState(true)

  // Auto-hide 2 seconds after environment becomes running;
  // reset visibility (via timeout) when status goes back to non-running.
  useEffect(() => {
    if (status === 'running') {
      const t = setTimeout(() => setVisible(false), 2000)
      return () => clearTimeout(t)
    }
    const t = setTimeout(() => setVisible(true), 0)
    return () => clearTimeout(t)
  }, [status])

  if (!visible) return null

  const isReady = status === 'running'

  return (
    <Alert
      variant="light"
      color={isReady ? 'teal' : 'orange'}
      style={{
        borderRadius: 0,
        borderBottom: '1px solid var(--mantine-color-dark-5)',
        padding: '8px 16px',
      }}
    >
      <Text size="sm" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        {!isReady && <Loader size={14} color="orange" />}
        {isReady ? 'Ambiente pronto.' : messages[status]}
      </Text>
    </Alert>
  )
}
