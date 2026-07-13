import { Alert, Button, Code, Group, Modal, Stack, Text } from '@/components/ui/legacy'
import { IconAlertTriangle, IconCopy } from '@tabler/icons-react'
import styles from '../pages/mcp-server.module.css'

type Props = {
  serverName: string
  token: string
  clientId: string
  fallbackUrl: string
  copied: boolean
  clientIdCopied: boolean
  fallbackCopied: boolean
  opened: boolean
  onClose(): void
  onCopy(): void
  onCopyClientId(): void
  onCopyFallback(): void
}

export function McpTokenModal({
  serverName,
  token,
  clientId,
  fallbackUrl,
  copied,
  clientIdCopied,
  fallbackCopied,
  opened,
  onClose,
  onCopy,
  onCopyClientId,
  onCopyFallback,
}: Props) {
  return (
    <Modal
      opened={opened}
      onClose={onClose}
      title={serverName ? `Token MCP · ${serverName}` : 'Token MCP'}
      centered
      size="lg"
    >
      <Stack gap="md">
        <Alert color="yellow" icon={<IconAlertTriangle size={16} />}>
          O token completo aparece somente agora. Ao fechar esta janela, será necessário
          gerar um novo token para copiar novamente.
        </Alert>
        <div className={styles.tokenRevealBox}>
          <Text size="xs" c="dimmed" fw={700}>
            OAuth Client ID
          </Text>
          <Code className={styles.tokenRevealCode}>{clientId}</Code>
        </div>
        <div className={styles.tokenRevealBox}>
          <Text size="xs" c="dimmed" fw={700}>
            OAuth Client Secret / Token MCP
          </Text>
          <Code className={styles.tokenRevealCode}>{token}</Code>
        </div>
        <div className={styles.tokenRevealBox}>
          <Text size="xs" c="dimmed" fw={700}>
            URL com token para fallback
          </Text>
          <Code className={styles.tokenRevealCode}>{fallbackUrl}</Code>
        </div>
        <Group justify="flex-end">
          <Button variant="subtle" onClick={onClose}>
            Fechar
          </Button>
          <Button variant="light" leftSection={<IconCopy size={16} />} onClick={onCopyFallback}>
            {fallbackCopied ? 'URL copiada' : 'Copiar URL com token'}
          </Button>
          <Button variant="light" leftSection={<IconCopy size={16} />} onClick={onCopyClientId}>
            {clientIdCopied ? 'Client ID copiado' : 'Copiar Client ID'}
          </Button>
          <Button leftSection={<IconCopy size={16} />} onClick={onCopy}>
            {copied ? 'Secret copiado' : 'Copiar Client Secret'}
          </Button>
        </Group>
      </Stack>
    </Modal>
  )
}
