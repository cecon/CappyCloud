import { useEffect, useState } from 'react'
import {
  Alert,
  Badge,
  Button,
  Checkbox,
  Drawer,
  Group,
  Loader,
  Stack,
  Tabs,
  Text,
  Title,
} from '@mantine/core'
import {
  type AdminUser,
  type AiModel,
  bulkGrantAiModelsByTier,
  errorToUserMessage,
  fetchAdminModels,
  fetchRepositories,
  fetchSandboxes,
  fetchUserAiModelAccess,
  fetchUserRepositoryAccess,
  fetchUserSandboxAccess,
  getToken,
  grantUserAiModelAccess,
  grantUserRepositoryAccess,
  grantUserSandboxAccess,
  type ModelTier,
  type Repository,
  revokeUserAiModelAccess,
  revokeUserRepositoryAccess,
  revokeUserSandboxAccess,
  type Sandbox,
} from '../api'

type Props = {
  user: AdminUser | null
  onClose: () => void
}

type Pair<T> = {
  available: T[] | null
  allowed: Set<string>
  busy: Set<string>
}

const EMPTY = <T,>(): Pair<T> => ({ available: null, allowed: new Set(), busy: new Set() })

export function UserAccessDrawer({ user, onClose }: Props) {
  const [sandboxes, setSandboxes] = useState<Pair<Sandbox>>(EMPTY())
  const [repos, setRepos] = useState<Pair<Repository>>(EMPTY())
  const [models, setModels] = useState<Pair<AiModel>>(EMPTY())
  const [bulkBusy, setBulkBusy] = useState<ModelTier | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!user) return
    const token = getToken()
    if (!token) return
    setSandboxes(EMPTY())
    setRepos(EMPTY())
    setModels(EMPTY())
    setError(null)

    void (async () => {
      try {
        const [allSandboxes, sbAllowed, allRepos, repoAllowed, allModels, modelAllowed] =
          await Promise.all([
            fetchSandboxes(token),
            fetchUserSandboxAccess(token, user.id),
            fetchRepositories(token),
            fetchUserRepositoryAccess(token, user.id),
            fetchAdminModels(token, { only_active: true }),
            fetchUserAiModelAccess(token, user.id),
          ])
        setSandboxes({ available: allSandboxes, allowed: new Set(sbAllowed), busy: new Set() })
        setRepos({ available: allRepos, allowed: new Set(repoAllowed), busy: new Set() })
        setModels({ available: allModels, allowed: new Set(modelAllowed), busy: new Set() })
      } catch (err) {
        setError(errorToUserMessage(err))
      }
    })()
  }, [user])

  async function toggleAccess<T>(
    state: Pair<T>,
    setState: (s: Pair<T>) => void,
    resourceId: string,
    grant: (token: string, userId: string, rid: string) => Promise<void>,
    revoke: (token: string, userId: string, rid: string) => Promise<void>,
  ) {
    if (!user) return
    const token = getToken()
    if (!token) return
    const wasAllowed = state.allowed.has(resourceId)
    const nextBusy = new Set(state.busy)
    nextBusy.add(resourceId)
    setState({ ...state, busy: nextBusy })
    setError(null)
    try {
      if (wasAllowed) {
        await revoke(token, user.id, resourceId)
      } else {
        await grant(token, user.id, resourceId)
      }
      const nextAllowed = new Set(state.allowed)
      if (wasAllowed) nextAllowed.delete(resourceId)
      else nextAllowed.add(resourceId)
      const newBusy = new Set(nextBusy)
      newBusy.delete(resourceId)
      setState({ ...state, allowed: nextAllowed, busy: newBusy })
    } catch (err) {
      setError(errorToUserMessage(err))
      const newBusy = new Set(nextBusy)
      newBusy.delete(resourceId)
      setState({ ...state, busy: newBusy })
    }
  }

  async function bulkByTier(tier: ModelTier) {
    if (!user) return
    const token = getToken()
    if (!token) return
    setBulkBusy(tier)
    setError(null)
    try {
      await bulkGrantAiModelsByTier(token, user.id, tier)
      // Reload allowed model ids:
      const allowed = await fetchUserAiModelAccess(token, user.id)
      setModels((prev) => ({ ...prev, allowed: new Set(allowed) }))
    } catch (err) {
      setError(errorToUserMessage(err))
    } finally {
      setBulkBusy(null)
    }
  }

  return (
    <Drawer
      opened={user !== null}
      onClose={onClose}
      position="right"
      size="xl"
      title={
        user ? (
          <Stack gap={2}>
            <Title order={4}>Acessos · {user.email}</Title>
            <Text size="xs" c="dimmed">
              ADMIN vê tudo; USER vê apenas os recursos selecionados aqui.
            </Text>
          </Stack>
        ) : null
      }
    >
      {user && (
        <Stack gap="md">
          {error && (
            <Alert color="red" title="Falha" withCloseButton onClose={() => setError(null)}>
              {error}
            </Alert>
          )}
          <Tabs defaultValue="sandboxes" keepMounted={false}>
            <Tabs.List>
              <Tabs.Tab value="sandboxes">Sandboxes</Tabs.Tab>
              <Tabs.Tab value="repos">Repositórios</Tabs.Tab>
              <Tabs.Tab value="models">Modelos LLM</Tabs.Tab>
            </Tabs.List>

            <Tabs.Panel value="sandboxes" pt="md">
              <AccessList
                available={sandboxes.available}
                allowed={sandboxes.allowed}
                busy={sandboxes.busy}
                renderLabel={(s) => (
                  <Group gap="xs">
                    <Text fw={500}>{s.name}</Text>
                    <Badge size="xs" variant="light" color="gray">
                      {s.host}
                    </Badge>
                  </Group>
                )}
                onToggle={(id) =>
                  toggleAccess(
                    sandboxes,
                    setSandboxes,
                    id,
                    grantUserSandboxAccess,
                    revokeUserSandboxAccess,
                  )
                }
              />
            </Tabs.Panel>

            <Tabs.Panel value="repos" pt="md">
              <AccessList
                available={repos.available}
                allowed={repos.allowed}
                busy={repos.busy}
                renderLabel={(r) => (
                  <Group gap="xs">
                    <Text fw={500}>{r.name}</Text>
                    <Badge size="xs" variant="light" color="gray">
                      {r.slug}
                    </Badge>
                  </Group>
                )}
                onToggle={(id) =>
                  toggleAccess(
                    repos,
                    setRepos,
                    id,
                    grantUserRepositoryAccess,
                    revokeUserRepositoryAccess,
                  )
                }
              />
            </Tabs.Panel>

            <Tabs.Panel value="models" pt="md">
              <Stack gap="sm">
                <Group justify="space-between">
                  <Text size="sm" c="dimmed">
                    {models.allowed.size} de {models.available?.length ?? 0} modelos liberados.
                  </Text>
                  <Group gap="xs">
                    <Button
                      size="xs"
                      variant="light"
                      loading={bulkBusy === 'free'}
                      disabled={bulkBusy !== null}
                      onClick={() => void bulkByTier('free')}
                    >
                      Liberar todos free
                    </Button>
                    <Button
                      size="xs"
                      variant="light"
                      color="grape"
                      loading={bulkBusy === 'paid'}
                      disabled={bulkBusy !== null}
                      onClick={() => void bulkByTier('paid')}
                    >
                      Liberar todos paid
                    </Button>
                  </Group>
                </Group>
                <AccessList
                  available={models.available}
                  allowed={models.allowed}
                  busy={models.busy}
                  renderLabel={(m) => (
                    <Group gap="xs">
                      <Text fw={500}>{m.display_name}</Text>
                      <Badge
                        size="xs"
                        variant="light"
                        color={m.tier === 'free' ? 'green' : m.tier === 'paid' ? 'grape' : 'gray'}
                      >
                        {m.tier}
                      </Badge>
                    </Group>
                  )}
                  onToggle={(id) =>
                    toggleAccess(
                      models,
                      setModels,
                      id,
                      grantUserAiModelAccess,
                      revokeUserAiModelAccess,
                    )
                  }
                />
              </Stack>
            </Tabs.Panel>
          </Tabs>
        </Stack>
      )}
    </Drawer>
  )
}

type AccessListProps<T extends { id: string }> = {
  available: T[] | null
  allowed: Set<string>
  busy: Set<string>
  renderLabel: (item: T) => React.ReactNode
  onToggle: (id: string) => void
}

function AccessList<T extends { id: string }>({
  available,
  allowed,
  busy,
  renderLabel,
  onToggle,
}: AccessListProps<T>) {
  if (available === null) {
    return (
      <Group justify="center" py="xl">
        <Loader size="sm" />
      </Group>
    )
  }
  if (available.length === 0) {
    return (
      <Text c="dimmed" ta="center" py="xl" size="sm">
        Nenhum recurso cadastrado.
      </Text>
    )
  }
  return (
    <Stack gap="xs">
      {available.map((item) => (
        <Group key={item.id} justify="space-between" wrap="nowrap">
          <Checkbox
            checked={allowed.has(item.id)}
            disabled={busy.has(item.id)}
            onChange={() => onToggle(item.id)}
            label={renderLabel(item)}
          />
          {busy.has(item.id) && <Loader size="xs" />}
        </Group>
      ))}
    </Stack>
  )
}
