import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Alert,
  Button,
  Container,
  Group,
  Loader,
  Paper,
  SimpleGrid,
  Stack,
  Text,
  Title,
} from '@mantine/core'
import {
  IconPlus,
  IconServer2,
} from '@tabler/icons-react'
import {
  createUserMcpServer,
  deleteUserMcpServer,
  errorToUserMessage,
  fetchRepositories,
  fetchUserMcpServers,
  getToken,
  rotateUserMcpServerToken,
  updateUserMcpServer,
  type Repository,
  type UserMcpServer,
  type UserMcpServerPayload,
} from '../api'
import { McpConnectionPanel } from '../components/McpConnectionPanel'
import {
  McpServerFormModal,
  type McpServerFormState,
} from '../components/McpServerFormModal'
import { McpTokenModal } from '../components/McpTokenModal'
import { UserMcpServerCard } from '../components/UserMcpServerCard'
import { copyText } from '../lib/clipboard'
import styles from './mcp-server.module.css'

type SecretState = {
  serverId: string
  serverName: string
  token: string
}

const EMPTY_FORM: McpServerFormState = { name: '', repository_id: '', enabled: true }
const PUBLIC_BASE_KEY = 'cappycloud_mcp_public_base_url'

function isLocalUrl(value: string): boolean {
  try {
    const host = new URL(value).hostname
    return ['localhost', '127.0.0.1', '::1'].includes(host)
  } catch {
    return false
  }
}

function normaliseBaseUrl(value: string): string {
  return value.trim().replace(/\/+$/, '')
}

function endpointUrl(serverId: string, publicBaseUrl: string): string {
  const base = normaliseBaseUrl(publicBaseUrl) || window.location.origin
  return `${base}/api/mcp/servers/${serverId}`
}

function fallbackEndpointUrl(serverId: string, publicBaseUrl: string, token: string): string {
  const base = normaliseBaseUrl(publicBaseUrl) || window.location.origin
  return `${base}/api/mcp/token/${encodeURIComponent(token)}/servers/${serverId}`
}

function staticClientId(serverId: string): string {
  return serverId
}

function payloadFromForm(form: McpServerFormState): UserMcpServerPayload {
  return {
    name: form.name.trim(),
    repository_id: form.repository_id,
    enabled: form.enabled,
  }
}

export function McpServerPage() {
  const [servers, setServers] = useState<UserMcpServer[] | null>(null)
  const [repos, setRepos] = useState<Repository[]>([])
  const [loadError, setLoadError] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [busyId, setBusyId] = useState<string | null>(null)
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState<UserMcpServer | null>(null)
  const [form, setForm] = useState<McpServerFormState>(EMPTY_FORM)
  const [saving, setSaving] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)
  const [secret, setSecret] = useState<SecretState | null>(null)
  const [copied, setCopied] = useState<string | null>(null)
  const [publicBaseUrl, setPublicBaseUrl] = useState(() => {
    return window.localStorage.getItem(PUBLIC_BASE_KEY) ?? ''
  })

  const reload = useCallback(async () => {
    const token = getToken()
    if (!token) return
    try {
      const [serverRows, repoRows] = await Promise.all([
        fetchUserMcpServers(token),
        fetchRepositories(token),
      ])
      setServers(serverRows)
      setRepos(repoRows)
      setLoadError(null)
    } catch (err) {
      setLoadError(errorToUserMessage(err))
    }
  }, [])

  useEffect(() => {
    void reload()
  }, [reload])

  const repoById = useMemo(() => new Map(repos.map((repo) => [repo.id, repo])), [repos])
  const repoOptions = repos.map((repo) => ({
    value: repo.id,
    label: `${repo.name} · ${repo.slug}`,
  }))

  function openCreate() {
    setEditing(null)
    setForm({ ...EMPTY_FORM, repository_id: repos[0]?.id ?? '' })
    setFormError(null)
    setModalOpen(true)
  }

  function openEdit(server: UserMcpServer) {
    setEditing(server)
    setForm({
      name: server.name,
      repository_id: server.repository_id,
      enabled: server.enabled,
    })
    setFormError(null)
    setModalOpen(true)
  }

  async function save() {
    const token = getToken()
    if (!token) return
    if (!form.name.trim() || !form.repository_id) {
      setFormError('Nome e repositório são obrigatórios.')
      return
    }
    setSaving(true)
    setFormError(null)
    try {
      if (editing) {
        await updateUserMcpServer(token, editing.id, payloadFromForm(form))
      } else {
        const created = await createUserMcpServer(token, payloadFromForm(form))
        setSecret({ serverId: created.id, serverName: created.name, token: created.token })
      }
      setModalOpen(false)
      setForm(EMPTY_FORM)
      setEditing(null)
      await reload()
    } catch (err) {
      setFormError(errorToUserMessage(err))
    } finally {
      setSaving(false)
    }
  }

  async function rotateToken(server: UserMcpServer) {
    const token = getToken()
    if (!token) return
    if (!window.confirm('Rotacionar o token deste MCP server? O token anterior deixará de funcionar.')) {
      return
    }
    setBusyId(server.id)
    setActionError(null)
    try {
      const rotated = await rotateUserMcpServerToken(token, server.id)
      setSecret({ serverId: server.id, serverName: rotated.name, token: rotated.token })
      await reload()
    } catch (err) {
      setActionError(errorToUserMessage(err))
    } finally {
      setBusyId(null)
    }
  }

  async function remove(server: UserMcpServer) {
    const token = getToken()
    if (!token) return
    if (!window.confirm('Remover este MCP server?')) return
    setBusyId(server.id)
    setActionError(null)
    try {
      await deleteUserMcpServer(token, server.id)
      if (secret?.serverId === server.id) setSecret(null)
      await reload()
    } catch (err) {
      setActionError(errorToUserMessage(err))
    } finally {
      setBusyId(null)
    }
  }

  async function copy(value: string, key: string) {
    if (await copyText(value)) {
      setActionError(null)
      setCopied(key)
      window.setTimeout(() => setCopied(null), 1400)
    } else {
      setActionError('Não foi possível copiar automaticamente. Selecione o texto e copie manualmente.')
    }
  }

  function updatePublicBaseUrl(value: string) {
    setPublicBaseUrl(value)
    const normalised = normaliseBaseUrl(value)
    if (normalised) {
      window.localStorage.setItem(PUBLIC_BASE_KEY, normalised)
    } else {
      window.localStorage.removeItem(PUBLIC_BASE_KEY)
    }
  }

  const loading = servers === null
  const endpointBaseUrl = normaliseBaseUrl(publicBaseUrl) || window.location.origin
  const usingLocalEndpoint = isLocalUrl(endpointBaseUrl)

  return (
    <Container size="xl" py="xl">
      <Stack gap="lg">
        <Group justify="space-between" align="flex-end">
          <Stack gap={4}>
            <Title order={2}>MCP Server</Title>
            <Text c="dimmed" size="sm">
              Endpoints HTTP com token próprio para LLMs externas consultarem repositórios.
            </Text>
          </Stack>
          <Button leftSection={<IconPlus size={16} />} onClick={openCreate} disabled={repos.length === 0}>
            Novo MCP
          </Button>
        </Group>

        {loadError && <Alert color="red" title="Falha ao carregar">{loadError}</Alert>}
        {actionError && (
          <Alert color="red" title="Falha" withCloseButton onClose={() => setActionError(null)}>
            {actionError}
          </Alert>
        )}
        <McpConnectionPanel
          publicBaseUrl={publicBaseUrl}
          usingLocalEndpoint={usingLocalEndpoint}
          onChange={updatePublicBaseUrl}
        />

        {loading ? (
          <div className={styles.loading}>
            <Loader size="sm" />
          </div>
        ) : servers.length === 0 ? (
          <Paper className={styles.emptyState}>
            <IconServer2 size={24} />
            <Text fw={700}>Nenhum MCP server cadastrado.</Text>
            <Text c="dimmed" size="sm">
              Crie um endpoint para o repositório que será consultado pelo Claude.
            </Text>
          </Paper>
        ) : (
          <SimpleGrid cols={{ base: 1, md: 2 }} spacing="md">
            {servers.map((server) => {
              const repo = repoById.get(server.repository_id)
              return (
                <UserMcpServerCard
                  key={server.id}
                  server={server}
                  repo={repo}
                  endpoint={endpointUrl(server.id, publicBaseUrl)}
                  revealedToken={secret?.serverId === server.id ? secret.token : undefined}
                  busy={busyId === server.id}
                  copied={copied}
                  onEdit={openEdit}
                  onRotate={rotateToken}
                  onRemove={remove}
                  onCopy={copy}
                />
              )
            })}
          </SimpleGrid>
        )}
      </Stack>

      <McpServerFormModal
        opened={modalOpen}
        editing={editing !== null}
        form={form}
        repoOptions={repoOptions}
        formError={formError}
        saving={saving}
        onClose={() => setModalOpen(false)}
        onSave={save}
        onChange={setForm}
      />

      {secret && (
        <McpTokenModal
          opened
          serverName={secret.serverName}
          token={secret.token}
          clientId={staticClientId(secret.serverId)}
          fallbackUrl={fallbackEndpointUrl(secret.serverId, publicBaseUrl, secret.token)}
          copied={copied === `token:${secret.serverId}`}
          clientIdCopied={copied === `client-id:${secret.serverId}`}
          fallbackCopied={copied === `fallback-url:${secret.serverId}`}
          onClose={() => setSecret(null)}
          onCopy={() => copy(secret.token, `token:${secret.serverId}`)}
          onCopyClientId={() => copy(staticClientId(secret.serverId), `client-id:${secret.serverId}`)}
          onCopyFallback={() => (
            copy(
              fallbackEndpointUrl(secret.serverId, publicBaseUrl, secret.token),
              `fallback-url:${secret.serverId}`,
            )
          )}
        />
      )}
    </Container>
  )
}
