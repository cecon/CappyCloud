import { Group, Text } from '@mantine/core'
import styles from './chat.module.css'

interface ThinkingIndicatorProps {
  /** Texto alternativo ao "A pensar…" padrão */
  label?: string
}

export function ThinkingIndicator({ label }: ThinkingIndicatorProps = {}) {
  return (
    <Group gap="xs" align="center">
      <Group gap={5} align="center">
        <div className={styles.thinkingDot} />
        <div className={styles.thinkingDot} />
        <div className={styles.thinkingDot} />
      </Group>
      <Text size="sm" c="dimmed">
        {label ?? 'A pensar…'}
      </Text>
    </Group>
  )
}
