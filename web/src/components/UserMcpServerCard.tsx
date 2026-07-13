import { Badge, Button, Code, Group, Paper, Stack, Text, Title } from '@/components/ui/legacy'
import {
  IconCopy,
  IconKey,
  IconPencil,
  IconRefresh,
  IconTrash,
} from '@tabler/icons-react'
import type { Repository, UserMcpServer } from '../api'
import styles from '../pages/mcp-server.module.css'

const TOOL_LABELS = ['read', 'search', 'grep', 'skills', 'confluence']

type Props = {
  server: UserMcpServer
  repo: Repository | undefined
  endpoint: string
  revealedToken?: string
  busy: boolean
  copied: string | null
  onEdit(server: UserMcpServer): void
  onRotate(server: UserMcpServer): void
  onRemove(server: UserMcpServer): void
  onCopy(value: string, key: string): void
}

export function UserMcpServerCard({
  server,
  repo,
  endpoint,
  revealedToken,
  busy,
  copied,
  onEdit,
  onRotate,
  onRemove,
  onCopy,
}: Props) {
  const clientId = server.id

  return (
    <Paper className={styles.serverCard}>
      <Stack gap="md">
        <Group justify="space-between" align="flex-start">
          <Stack gap={4} className={styles.cardTitle}>
            <Group gap="xs">
              <Title order={3}>{server.name}</Title>
              <Badge color={server.enabled ? 'green' : 'gray'} variant="light">
                {server.enabled ? 'Ativo' : 'Pausado'}
              </Badge>
            </Group>
            <Text c="dimmed" size="sm">
              {repo ? `${repo.name} · ${repo.slug}` : server.repository_id}
            </Text>
          </Stack>
          <Group gap={6}>
            <Button variant="subtle" size="xs" onClick={() => onEdit(server)} aria-label="Editar">
              <IconPencil size={15} />
            </Button>
            <Button
              variant="subtle"
              size="xs"
              loading={busy}
              onClick={() => onRotate(server)}
              aria-label="Rotacionar token"
            >
              <IconRefresh size={15} />
            </Button>
            <Button
              variant="subtle"
              color="red"
              size="xs"
              loading={busy}
              onClick={() => onRemove(server)}
              aria-label="Remover"
            >
              <IconTrash size={15} />
            </Button>
          </Group>
        </Group>

        <div className={styles.endpointBox}>
          <Text size="xs" c="dimmed" fw={700}>
            URL do servidor MCP remoto
          </Text>
          <Group gap="xs" wrap="nowrap">
            <Code className={styles.endpointCode}>{endpoint}</Code>
            <Button
              size="xs"
              variant="light"
              onClick={() => onCopy(endpoint, `url:${server.id}`)}
              leftSection={<IconCopy size={14} />}
            >
              {copied === `url:${server.id}` ? 'Copiado' : 'Copiar'}
            </Button>
          </Group>
        </div>

        <div className={styles.endpointBox}>
          <Text size="xs" c="dimmed" fw={700}>
            OAuth Client ID
          </Text>
          <Group gap="xs" wrap="nowrap">
            <Code className={styles.endpointCode}>{clientId}</Code>
            <Button
              size="xs"
              variant="light"
              onClick={() => onCopy(clientId, `client-id:${server.id}`)}
              leftSection={<IconCopy size={14} />}
            >
              {copied === `client-id:${server.id}` ? 'Copiado' : 'Copiar'}
            </Button>
          </Group>
        </div>

        <Group gap="xs">
          <Badge variant="outline" leftSection={<IconKey size={12} />}>
            ...{server.token_preview}
          </Badge>
          {revealedToken ? (
            <Button
              size="xs"
              variant="light"
              leftSection={<IconCopy size={14} />}
              onClick={() => onCopy(revealedToken, `token:${server.id}`)}
            >
              {copied === `token:${server.id}` ? 'Copiado' : 'Copiar secret'}
            </Button>
          ) : (
            <Button
              size="xs"
              variant="light"
              loading={busy}
              leftSection={<IconRefresh size={14} />}
              onClick={() => onRotate(server)}
            >
              Gerar novo token
            </Button>
          )}
          {TOOL_LABELS.map((tool) => (
            <Badge key={tool} variant="light" color="blue">
              {tool}
            </Badge>
          ))}
        </Group>
      </Stack>
    </Paper>
  )
}
