import { useState } from 'react'
import { Badge, Code, Collapse, Group, Text } from '@mantine/core'
import styles from './chat.module.css'

export type ToolCallState = {
  id: string
  name: string
  input: string
  output?: string
  isError?: boolean
  done: boolean
}

interface Props {
  tool: ToolCallState
}

export function ToolCallCard({ tool }: Props) {
  const [open, setOpen] = useState(false)

  let inputDisplay: string
  try {
    const parsed = JSON.parse(tool.input)
    inputDisplay = JSON.stringify(parsed, null, 2)
  } catch {
    inputDisplay = tool.input
  }

  const borderColor = tool.done
    ? tool.isError
      ? 'var(--mantine-color-red-8)'
      : 'var(--mantine-color-dark-4)'
    : 'var(--mantine-color-teal-8)'

  return (
    <div
      className={styles.toolCard}
      style={{
        border: `1px solid ${borderColor}`,
        borderRadius: 8,
        overflow: 'hidden',
        maxWidth: '92%',
        animation: 'fadeInUp 0.2s ease both',
      }}
    >
      {/* Header row */}
      <div
        className={tool.done ? styles.toolHeader : undefined}
        onClick={() => tool.done && setOpen((o) => !o)}
        style={{ background: 'var(--mantine-color-dark-7)' }}
      >
        <Group px="sm" py={6} gap="xs">
          {tool.done ? (
            tool.isError ? (
              <Text size="sm" c="red" lh={1}>
                ✗
              </Text>
            ) : (
              <Text size="sm" c="teal" lh={1}>
                ✓
              </Text>
            )
          ) : (
            <div className={styles.spinner} />
          )}

          <Text
            size="xs"
            fw={500}
            c="dimmed"
            style={{ fontFamily: 'monospace', flex: 1 }}
          >
            {tool.name}
          </Text>

          {tool.done ? (
            <Text size="xs" c="dimmed">
              {open ? '▲' : '▼'}
            </Text>
          ) : (
            <Badge size="xs" variant="dot" color="teal">
              a executar
            </Badge>
          )}
        </Group>
      </div>

      {/* Collapsible detail */}
      <Collapse expanded={open && tool.done}>
        <div style={{ padding: '8px 12px', background: 'var(--mantine-color-dark-8)' }}>
          {inputDisplay && (
            <>
              <Text size="xs" c="dimmed" mb={4} tt="uppercase" fw={600} style={{ letterSpacing: '0.04em' }}>
                Entrada
              </Text>
              <Code block style={{ fontSize: 11, maxHeight: 140, overflow: 'auto' }}>
                {inputDisplay}
              </Code>
            </>
          )}
          {tool.output !== undefined && (
            <div style={{ marginTop: inputDisplay ? 10 : 0 }}>
              <Text
                size="xs"
                c={tool.isError ? 'red' : 'dimmed'}
                mb={4}
                tt="uppercase"
                fw={600}
                style={{ letterSpacing: '0.04em' }}
              >
                {tool.isError ? 'Saída (erro)' : 'Saída'}
              </Text>
              <Code
                block
                style={{
                  fontSize: 11,
                  maxHeight: 180,
                  overflow: 'auto',
                  color: tool.isError ? 'var(--mantine-color-red-4)' : undefined,
                }}
              >
                {tool.output}
              </Code>
            </div>
          )}
        </div>
      </Collapse>
    </div>
  )
}
