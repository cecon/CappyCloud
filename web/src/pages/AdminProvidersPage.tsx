import { useCallback, useEffect, useState } from 'react'
import {
  Alert,
  Badge,
  Container,
  Group,
  Loader,
  Paper,
  Stack,
  Table,
  Text,
  Title,
} from '@mantine/core'
import { IconRefresh } from '@tabler/icons-react'
import {
  type AdminAiProvider,
  type AiModelSyncResult,
  errorToUserMessage,
  fetchAdminProviders,
  getToken,
  syncAdminProvider,
} from '../api'
import { ActionsCell, ActionsHeader, RowActionIcon } from '../components/TableActions'
import { useCurrentUser } from '../hooks/useCurrentUser'

function formatTimestamp(iso: string | null): string {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleString('pt-PT')
  } catch {
    return iso
  }
}

export function AdminProvidersPage() {
  const currentUser = useCurrentUser()
  const canSyncProviders =
    currentUser.status === 'ready' && currentUser.user.is_super_admin
  const [providers, setProviders] = useState<AdminAiProvider[] | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [syncing, setSyncing] = useState<string | null>(null)
  const [lastResult, setLastResult] = useState<AiModelSyncResult | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)

  const reload = useCallback(async () => {
    const token = getToken()
    if (!token) return
    try {
      const list = await fetchAdminProviders(token)
      setProviders(list)
      setLoadError(null)
    } catch (err) {
      setLoadError(errorToUserMessage(err))
    }
  }, [])

  useEffect(() => {
    void reload()
  }, [reload])

  async function handleSync(providerId: string) {
    const token = getToken()
    if (!token) return
    setSyncing(providerId)
    setActionError(null)
    setLastResult(null)
    try {
      const result = await syncAdminProvider(token, providerId)
      setLastResult(result)
      await reload()
    } catch (err) {
      setActionError(errorToUserMessage(err))
    } finally {
      setSyncing(null)
    }
  }

  return (
    <Container size="lg" py="xl">
      <Stack gap="lg">
        <Stack gap={4}>
          <Title order={2}>Providers LLM</Title>
          <Text c="dimmed" size="sm">
            Provedores de modelos IA (OpenRouter, Anthropic, OpenAI...). O sync busca o catálogo
            do provider e atualiza os modelos disponíveis na plataforma.
          </Text>
        </Stack>

        {actionError && (
          <Alert color="red" title="Falha no sync" withCloseButton onClose={() => setActionError(null)}>
            {actionError}
          </Alert>
        )}

        {!canSyncProviders && (
          <Alert color="yellow" title="Somente super admin sincroniza providers">
            A sincronização pode ativar novos modelos free e atualizar preços globais.
          </Alert>
        )}

        {lastResult && (
          <Alert color="green" title="Sync concluído" withCloseButton onClose={() => setLastResult(null)}>
            {lastResult.fetched} modelos do provider — {lastResult.created} criados,{' '}
            {lastResult.updated} atualizados, {lastResult.deactivated} desativados.
          </Alert>
        )}

        <Paper withBorder p="md" radius="md">
          {loadError ? (
            <Alert color="red" title="Não foi possível carregar providers">
              {loadError}
            </Alert>
          ) : providers === null ? (
            <Group justify="center" py="xl">
              <Loader />
            </Group>
          ) : providers.length === 0 ? (
            <Text c="dimmed" ta="center" py="xl">
              Nenhum provider cadastrado.
            </Text>
          ) : (
            <Table verticalSpacing="sm" highlightOnHover>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Nome</Table.Th>
                  <Table.Th>Base URL</Table.Th>
                  <Table.Th style={{ width: 90 }}>Modelos</Table.Th>
                  <Table.Th style={{ width: 90 }}>Estado</Table.Th>
                  <Table.Th style={{ width: 180 }}>Último sync</Table.Th>
                  <ActionsHeader width={72} />
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {providers.map((p) => (
                  <Table.Tr key={p.id}>
                    <Table.Td>
                      <Text fw={500}>{p.name}</Text>
                    </Table.Td>
                    <Table.Td>
                      <Text size="xs" c="dimmed">
                        {p.base_url}
                      </Text>
                    </Table.Td>
                    <Table.Td>
                      <Badge variant="light" color="blue">
                        {p.models_count}
                      </Badge>
                    </Table.Td>
                    <Table.Td>
                      <Badge color={p.active ? 'green' : 'gray'} variant={p.active ? 'filled' : 'light'}>
                        {p.active ? 'ativo' : 'inativo'}
                      </Badge>
                    </Table.Td>
                    <Table.Td>
                      <Text size="xs">{formatTimestamp(p.last_synced_at)}</Text>
                    </Table.Td>
                    <ActionsCell>
                      <RowActionIcon
                        label="Sincronizar provider"
                        color="blue"
                        loading={syncing === p.id}
                        disabled={!canSyncProviders || syncing !== null || !p.active}
                        onClick={() => void handleSync(p.id)}
                      >
                        <IconRefresh size={16} />
                      </RowActionIcon>
                    </ActionsCell>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          )}
        </Paper>
      </Stack>
    </Container>
  )
}
