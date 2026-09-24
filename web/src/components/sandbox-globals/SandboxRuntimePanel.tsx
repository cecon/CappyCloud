import { useCallback, useEffect, useState } from 'react'
import { Alert, Badge, Button, Code, Group, Select, Stack, Text } from '@/components/ui/legacy'
import {
  errorToUserMessage,
  fetchSandboxClaudeStatus,
  getToken,
  updateAdminSandbox,
  type AgentRuntime,
  type Sandbox,
  type SandboxClaudeStatus,
} from '../../api'

type Props = {
  sandbox: Sandbox
  onUpdated: (sandbox: Sandbox) => void
}

const RUNTIME_OPTIONS: Array<{ value: AgentRuntime; label: string }> = [
  { value: 'openclaude', label: 'openclaude (modelos do catálogo via OpenRouter/provider)' },
  { value: 'claude_cli', label: 'Claude CLI oficial (conta do `claude login`)' },
]

/**
 * Escolhe o runtime do agente desta sandbox e mostra se o Claude CLI está
 * pronto (instalado e com `claude login` feito). A troca vale a partir da
 * próxima mensagem, inclusive em conversas abertas.
 */
export function SandboxRuntimePanel({ sandbox, onUpdated }: Props) {
  const current: AgentRuntime = sandbox.agent_runtime ?? 'openclaude'
  const [draft, setDraft] = useState<AgentRuntime>(current)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [status, setStatus] = useState<SandboxClaudeStatus | null>(null)
  const [statusLoading, setStatusLoading] = useState(false)

  useEffect(() => {
    setDraft(sandbox.agent_runtime ?? 'openclaude')
    setError(null)
  }, [sandbox.id, sandbox.agent_runtime])

  const loadStatus = useCallback(async () => {
    const token = getToken()
    if (!token) return
    setStatusLoading(true)
    try {
      setStatus(await fetchSandboxClaudeStatus(token, sandbox.id))
    } catch (err) {
      setStatus({ reachable: false, error: errorToUserMessage(err) })
    } finally {
      setStatusLoading(false)
    }
  }, [sandbox.id])

  useEffect(() => {
    void loadStatus()
  }, [loadStatus])

  async function save() {
    const token = getToken()
    if (!token) return
    setSaving(true)
    setError(null)
    try {
      onUpdated(await updateAdminSandbox(token, sandbox.id, { agent_runtime: draft }))
    } catch (err) {
      setError(errorToUserMessage(err))
    } finally {
      setSaving(false)
    }
  }

  const claudeReady = !!status?.reachable && !!status.installed && !!status.logged_in

  return (
    <Stack gap="md">
      {error && (
        <Alert color="red" title="Não foi possível salvar">
          {error}
        </Alert>
      )}
      <Text size="sm" c="dimmed">
        Define qual agente atende as conversas desta sandbox. A troca vale a partir da próxima
        mensagem.
      </Text>
      <Select
        label="Runtime do agente"
        data={RUNTIME_OPTIONS}
        value={draft}
        onChange={(value) => {
          if (value === 'openclaude' || value === 'claude_cli') setDraft(value)
        }}
        allowDeselect={false}
      />
      {draft === 'claude_cli' && status && !claudeReady && (
        <Alert color="yellow" title="Claude CLI ainda não está pronto">
          As conversas vão falhar até o Claude CLI estar instalado e autenticado nesta sandbox.
        </Alert>
      )}
      <Group justify="flex-end">
        <Button onClick={save} loading={saving} disabled={saving || draft === current}>
          Salvar
        </Button>
      </Group>

      <Stack gap="xs">
        <Group justify="space-between">
          <Text fw={600}>Claude CLI nesta sandbox</Text>
          <Button variant="subtle" size="xs" onClick={() => void loadStatus()} loading={statusLoading}>
            Verificar de novo
          </Button>
        </Group>
        {status && !status.reachable && (
          <Text size="sm" c="red">
            Sandbox não respondeu: {status.error ?? 'erro desconhecido'}
          </Text>
        )}
        {status?.reachable && (
          <Group gap="xs">
            <Badge color={status.installed ? 'green' : 'red'}>
              {status.installed ? `instalado ${status.version ?? ''}`.trim() : 'não instalado'}
            </Badge>
            <Badge color={status.logged_in ? 'green' : 'yellow'}>
              {status.logged_in ? 'login feito' : 'sem login'}
            </Badge>
          </Group>
        )}
        <Text size="sm" c="dimmed">
          Para autenticar com a sua assinatura: na listagem de sandboxes, clique no ícone de{' '}
          <b>terminal</b> desta sandbox → <b>Rodar claude login</b>, abra o link e cole o código. As
          credenciais ficam em <Code>{status?.config_dir ?? '/root/.claude'}</Code>, que sobrevive a
          redeploys. Depois clique em “Verificar de novo”.
        </Text>
      </Stack>
    </Stack>
  )
}
