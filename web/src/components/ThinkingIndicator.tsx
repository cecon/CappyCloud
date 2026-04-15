import { Group, Text } from '@mantine/core'
import styles from './chat.module.css'

export function ThinkingIndicator() {
  return (
    <Group gap="xs" align="center">
      <Group gap={5} align="center">
        <div className={styles.thinkingDot} />
        <div className={styles.thinkingDot} />
        <div className={styles.thinkingDot} />
      </Group>
      <Text size="sm" c="dimmed">
        A pensar…
      </Text>
    </Group>
  )
}
