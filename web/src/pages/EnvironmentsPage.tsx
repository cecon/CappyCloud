import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  ActionIcon,
  Badge,
  Button,
  Card,
  Code,
  Container,
  Group,
  Loader,
  Modal,
  Stack,
  Text,
  TextInput,
  Title,
} from '@mantine/core'
import {
  type RepoEnv,
  type EnvStatus,
  createRepoEnvironment,
  deleteRepoEnvironment,
  errorToUserMessage,
  fetchRepoEnvironments,
  getRepoEnvironmentStatus,
  wakeRepoEnvironment,
} from '../api'

interface Props {
  token: string
}

/**
 * Página de gestão de ambientes de repositório globais.
 * Permite criar, listar, iniciar e remover ambientes (clones de repos git).
 */
export function EnvironmentsPage({ token }: Props) {
  const [envs, setEnvs] = useState<RepoEnv[]>([])
  const [loading, setLoading] = useState(true)
  const [statuses, setStatuses] = useState<Record<string, EnvStatus>>({})
  const [createOpen, setCreateOpen] = useState(false)
  const [creating, setCreating] = useState(false)
  const [createError, setCreateError] = useState<string | null>(null)

  const [slug, setSlug] = useState('')
  const [name, setName] = useState('')
  const [repoUrl, setRepoUrl] = useState('')
  const [branch, setBranch] = useState('main')

  async function load() {
    setLoading(true)
    try {
      const list = await fetchRepoEnvironments(token)
      setEnvs(list)
      // Load statuses in background
      const statusMap: Record<string, EnvStatus> = {}
      await Promise.all(
        list.map(async (e) => {
          const s = await getRepoEnvironmentStatus(token, e.id)
          statusMap[e.id] = s.status
        })
      )
      setStatuses(statusMap)
    } catch {
      // ignore
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function handleCreate() {
    const s = slug.trim()
    const n = name.trim()
    const r = repoUrl.trim()
    if (!s || !n || !r) {
      setCreateError('Preenche todos os campos obrigatórios.')
      return
    }
    setCreating(true)
    setCreateError(null)
    try {
      const env = await createRepoEnvironment(token, { slug: s, name: n, repo_url: r, branch: branch || 'main' })
      setEnvs((prev) => [...prev, env])
      setStatuses((prev) => ({ ...prev, [env.id]: 'none' }))
      setCreateOpen(false)
      setSlug('')
      setName('')
      setRepoUrl('')
      setBranch('main')
    } catch (e) {
      setCreateError(errorToUserMessage(e))
    } finally {
      setCreating(false)
    }
  }

  async function handleDelete(envId: string) {
    if (!confirm('Remover este ambiente? O container Docker será parado.')) return
    try {
      await deleteRepoEnvironment(token, envId)
      setEnvs((prev) => prev.filter((e) => e.id !== envId))
    } catch (e) {
      alert(errorToUserMessage(e))
    }
  }

  async function handleWake(envId: string) {
    setStatuses((prev) => ({ ...prev, [envId]: 'starting' }))
    await wakeRepoEnvironment(token, envId)
    // Poll until running
    let attempts = 0
    const poll = setInterval(async () => {
      attempts++
      const s = await getRepoEnvironmentStatus(token, envId)
      setStatuses((prev) => ({ ...prev, [envId]: s.status }))
      if (s.status === 'running' || attempts > 30) clearInterval(poll)
    }, 3000)
  }

  const statusColor: Record<EnvStatus, string> = {
    none: 'gray',
    stopped: 'orange',
    starting: 'blue',
    running: 'teal',
  }

  const statusLabel: Record<EnvStatus, string> = {
    none: 'Nunca iniciado',
    stopped: 'Parado',
    starting: 'Iniciando…',
    running: 'Em execução',
  }

  return (
    <Container size="md" py="xl">
        <Group justify="space-between" mb="lg">
        <Group gap="sm">
          <Button
            component={Link}
            to="/chat"
            variant="subtle"
            size="xs"
            color="gray"
            leftSection="←"
          >
            Voltar ao chat
          </Button>
          <Title order={2}>Ambientes</Title>
        </Group>
        <Group>
          <ActionIcon variant="subtle" onClick={load} title="Atualizar" size="lg">
            ↻
          </ActionIcon>
          <Button onClick={() => setCreateOpen(true)}>
            + Adicionar ambiente
          </Button>
        </Group>
      </Group>

      <Text c="dimmed" size="sm" mb="xl">
        Cada ambiente é um clone de um repositório git partilhado por todos os utilizadores.
        Cada conversa usa um git worktree isolado dentro do mesmo clone.
      </Text>

      {loading ? (
        <Group justify="center" py="xl">
          <Loader />
        </Group>
      ) : envs.length === 0 ? (
        <Card withBorder p="xl" ta="center">
          <Text c="dimmed" mb="md">Nenhum ambiente criado ainda.</Text>
          <Button onClick={() => setCreateOpen(true)}>Criar primeiro ambiente</Button>
        </Card>
      ) : (
        <Stack gap="md">
          {envs.map((env) => {
            const st = statuses[env.id] ?? 'none'
            return (
              <Card key={env.id} withBorder p="md">
                <Group justify="space-between" wrap="nowrap">
                  <Stack gap={4} style={{ flex: 1, minWidth: 0 }}>
                    <Group gap="xs">
                      <Text fw={600}>{env.name}</Text>
                      <Badge color={statusColor[st]} size="sm" variant="light">
                        {st === 'starting' ? (
                          <Group gap={4} align="center">
                            <Loader size={10} color={statusColor[st]} />
                            {statusLabel[st]}
                          </Group>
                        ) : (
                          statusLabel[st]
                        )}
                      </Badge>
                    </Group>
                    <Code style={{ fontSize: 12, wordBreak: 'break-all' }}>
                      {env.repo_url}
                    </Code>
                    <Group gap="xs">
                      <Text size="xs" c="dimmed" ff="monospace">⎇ {env.branch}</Text>
                      <Text size="xs" c="dimmed">·</Text>
                      <Text size="xs" c="dimmed" ff="monospace">{env.slug}</Text>
                    </Group>
                  </Stack>

                  <Group gap="xs" wrap="nowrap">
                    {st !== 'running' && st !== 'starting' && (
                      <Button
                        size="xs"
                        variant="light"
                        onClick={() => handleWake(env.id)}
                      >
                        Iniciar
                      </Button>
                    )}
                    <ActionIcon
                      color="red"
                      variant="subtle"
                      onClick={() => handleDelete(env.id)}
                      title="Remover ambiente"
                    >
                      ✕
                    </ActionIcon>
                  </Group>
                </Group>
              </Card>
            )
          })}
        </Stack>
      )}

      <Modal
        opened={createOpen}
        onClose={() => {
          setCreateOpen(false)
          setCreateError(null)
        }}
        title="Adicionar ambiente"
        size="md"
      >
        <Stack gap="sm">
          {createError && (
            <Text c="red" size="sm">{createError}</Text>
          )}
          <TextInput
            label="Nome"
            placeholder="Meu Projeto"
            value={name}
            onChange={(e) => setName(e.currentTarget.value)}
            required
          />
          <TextInput
            label="Slug"
            placeholder="meu-projeto"
            description="Minúsculas, números e hífens. Usado como nome do container e pasta."
            value={slug}
            onChange={(e) => setSlug(e.currentTarget.value.toLowerCase().replace(/[^a-z0-9-]/g, '-'))}
            required
          />
          <TextInput
            label="URL do repositório"
            placeholder="https://github.com/org/repo"
            value={repoUrl}
            onChange={(e) => setRepoUrl(e.currentTarget.value)}
            required
          />
          <TextInput
            label="Branch"
            placeholder="main"
            value={branch}
            onChange={(e) => setBranch(e.currentTarget.value)}
          />
          <Group justify="flex-end" mt="xs">
            <Button variant="subtle" onClick={() => setCreateOpen(false)}>
              Cancelar
            </Button>
            <Button loading={creating} onClick={handleCreate}>
              Criar
            </Button>
          </Group>
        </Stack>
      </Modal>
    </Container>
  )
}
