import { Alert, Paper, Stack, Text, TextInput } from '@mantine/core'
import { IconAlertTriangle } from '@tabler/icons-react'
import styles from '../pages/mcp-server.module.css'

type Props = {
  publicBaseUrl: string
  usingLocalEndpoint: boolean
  onChange(value: string): void
}

export function McpConnectionPanel({ publicBaseUrl, usingLocalEndpoint, onChange }: Props) {
  return (
    <Paper className={styles.connectionPanel}>
      <Stack gap="sm">
        <TextInput
          label="Base pública HTTPS"
          value={publicBaseUrl}
          onChange={(event) => onChange(event.currentTarget.value)}
          placeholder="https://seu-dominio-ou-tunel"
        />
        {usingLocalEndpoint && (
          <Alert color="yellow" icon={<IconAlertTriangle size={16} />}>
            Claude.ai não acessa localhost. Informe a URL pública HTTPS do túnel ou deploy
            antes de copiar a URL do servidor MCP remoto.
          </Alert>
        )}
        <Text size="sm" c="dimmed">
          No Claude.ai, preencha Nome e URL do servidor MCP remoto. Deixe ID do Cliente
          OAuth e Client Secret em branco.
        </Text>
      </Stack>
    </Paper>
  )
}
