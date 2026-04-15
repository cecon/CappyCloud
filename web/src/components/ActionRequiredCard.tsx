import { useState } from 'react'
import { Button, Group, Stack, Text, TextInput } from '@mantine/core'
import type { ActionRequiredEvent } from '../api'
import styles from './chat.module.css'

interface Props {
  action: ActionRequiredEvent
  onReply(reply: string): void
}

export function ActionRequiredCard({ action, onReply }: Props) {
  const [freeText, setFreeText] = useState('')
  const [replied, setReplied] = useState(false)

  function submit(reply: string) {
    if (replied) return
    setReplied(true)
    onReply(reply)
  }

  const isConfirm = action.action_type === 0
  const hasChoices = !isConfirm && action.choices && action.choices.length > 0

  return (
    <div
      className={styles.actionCard}
      style={{
        border: '1px solid var(--mantine-color-yellow-7)',
        borderRadius: 12,
        padding: '16px',
        background: 'var(--mantine-color-dark-7)',
        maxWidth: '92%',
        opacity: replied ? 0.5 : 1,
        transition: 'opacity 0.3s ease',
      }}
    >
      {/* Header */}
      <Group gap="xs" mb="sm" align="center">
        <Text size="lg" lh={1}>
          ⚠️
        </Text>
        <Text size="sm" fw={600} c="yellow">
          {isConfirm ? 'Confirmação necessária' : 'Informação necessária'}
        </Text>
      </Group>

      {/* Question */}
      <Text
        size="sm"
        mb="md"
        style={{
          whiteSpace: 'pre-wrap',
          lineHeight: 1.6,
          padding: '8px 12px',
          borderLeft: '2px solid var(--mantine-color-yellow-7)',
          background: 'var(--mantine-color-dark-8)',
          borderRadius: '0 6px 6px 0',
        }}
      >
        {action.question}
      </Text>

      {/* Action controls */}
      {isConfirm ? (
        /* ── Confirmation: Sim / Não ────────────────────────── */
        <Group gap="sm">
          <Button
            className={styles.actionButton}
            size="sm"
            color="green"
            variant="filled"
            onClick={() => submit('sim')}
            disabled={replied}
          >
            ✓ Sim
          </Button>
          <Button
            className={styles.actionButton}
            size="sm"
            color="red"
            variant="outline"
            onClick={() => submit('não')}
            disabled={replied}
          >
            ✗ Não
          </Button>
        </Group>
      ) : hasChoices ? (
        /* ── Multi-choice: numbered option buttons ──────────── */
        <Group gap="xs" wrap="wrap">
          {action.choices!.map((choice, i) => (
            <Button
              key={i}
              className={styles.actionButton}
              size="sm"
              variant="outline"
              color="teal"
              onClick={() => submit(String(i + 1))}
              disabled={replied}
            >
              {i + 1}. {choice}
            </Button>
          ))}
        </Group>
      ) : (
        /* ── Free text input ────────────────────────────────── */
        <Stack gap="xs">
          <TextInput
            size="sm"
            placeholder="A sua resposta…"
            value={freeText}
            onChange={(e) => setFreeText(e.currentTarget.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && freeText.trim()) submit(freeText.trim())
            }}
            disabled={replied}
          />
          <Button
            className={styles.actionButton}
            size="sm"
            onClick={() => freeText.trim() && submit(freeText.trim())}
            disabled={replied || !freeText.trim()}
          >
            Enviar resposta
          </Button>
        </Stack>
      )}
    </div>
  )
}
