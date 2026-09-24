import { useCallback, useEffect, useState } from 'react'
import { Alert, Badge, Button, Group, Loader, Modal, Stack, Table, Text } from '@/components/ui/legacy'
import {
  type AdminWorkspace,
  buildWorkspaceKnowledge,
  errorToUserMessage,
  fetchWorkspaceKnowledge,
  fetchWorkspaceKnowledgeFile,
  getToken,
  type KnowledgeFileContent,
  type KnowledgeStatus,
  type WorkspaceKnowledge,
} from '../api'

const STATE_LABEL: Record<KnowledgeStatus['state'], { text: string; color: string }> = {
  never_built: { text: 'Ainda não gerado', color: 'gray' },
  running: { text: 'Gerando…', color: 'blue' },
  done: { text: 'Atualizado', color: 'green' },
  partial: { text: 'Parcial', color: 'yellow' },
  error: { text: 'Erro', color: 'red' },
}

function formatWhen(iso?: string): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' })
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

function seconds(ms?: number): string {
  return ms === undefined ? '—' : `${(ms / 1000).toFixed(1)} s`
}

/** Status do grafo (graphify) e arquivos de knowledge/ e memory/ de um workspace. */
export function WorkspaceKnowledgeModal({ workspace, onClose }: { workspace: AdminWorkspace | null; onClose: () => void }) {
  const [data, setData] = useState<WorkspaceKnowledge | null>(null)
  const [error, setError] = useState<string | null>(null)
  // Momento do "Atualizar agora": segue acompanhando até o sandbox começar ou terminar.
  const [queuedAt, setQueuedAt] = useState<number | null>(null)
  const [file, setFile] = useState<KnowledgeFileContent | null>(null)
  const workspaceId = workspace?.id

  const load = useCallback(async () => {
    const token = getToken()
    if (!token || !workspaceId) return
    try {
      const next = await fetchWorkspaceKnowledge(token, workspaceId)
      setData(next)
      setError(null)
      const finished = next.status.finished_at ? Date.parse(next.status.finished_at) : 0
      setQueuedAt((at) => (at !== null && (next.status.running || finished >= at) ? null : at))
    } catch (err) {
      setError(errorToUserMessage(err))
    }
  }, [workspaceId])

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0)
    return () => window.clearTimeout(timer)
  }, [load])

  // Enquanto gera (ou logo depois de pedir), acompanha o status.
  const running = Boolean(data?.status.running || data?.status.state === 'running' || queuedAt !== null)
  useEffect(() => {
    if (!running) return
    const timer = window.setInterval(() => void load(), 5000)
    return () => window.clearInterval(timer)
  }, [running, load])

  async function rebuild() {
    const token = getToken()
    if (!token || !workspaceId) return
    try {
      await buildWorkspaceKnowledge(token, workspaceId)
      setQueuedAt(Date.now())
    } catch (err) {
      setError(errorToUserMessage(err))
    }
  }

  async function openFile(path: string) {
    const token = getToken()
    if (!token || !workspaceId) return
    try {
      setFile(await fetchWorkspaceKnowledgeFile(token, workspaceId, path))
    } catch (err) {
      setError(errorToUserMessage(err))
    }
  }

  const status = data?.status
  const label = status ? STATE_LABEL[status.running ? 'running' : status.state] : null

  return (
    <Modal opened={workspace !== null} onClose={onClose} title={`Conhecimento · ${workspace?.name ?? ''}`} size="xl">
      <Stack gap="md">
        {error && <Alert color="red">{error}</Alert>}
        {!data && !error && <Loader size="sm" />}
        {status && label && (
          <Stack gap="xs">
            <Group justify="space-between" wrap="wrap">
              <Group gap="xs">
                <Text fw={600}>Grafo de código (graphify)</Text>
                <Badge color={label.color} variant="light">
                  {label.text}
                </Badge>
              </Group>
              <Button size="xs" onClick={() => void rebuild()} loading={running} disabled={running}>
                Atualizar agora
              </Button>
            </Group>
            <Text size="sm" c="dimmed">
              Última geração: {formatWhen(status.finished_at)} · duração {seconds(status.duration_ms)} ·{' '}
              {status.nodes ?? 0} nós, {status.edges ?? 0} ligações. Atualiza sozinho depois de cada
              sincronização e todo dia às 4h.
            </Text>
            {status.error && <Alert color="red">{status.error}</Alert>}
            {status.repos && status.repos.length > 0 && (
              <Table verticalSpacing="xs">
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th>Repositório</Table.Th>
                    <Table.Th>Commit</Table.Th>
                    <Table.Th>Nós</Table.Th>
                    <Table.Th>Tempo</Table.Th>
                    <Table.Th>Observação</Table.Th>
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {status.repos.map((repo) => (
                    <Table.Tr key={repo.alias}>
                      <Table.Td>{repo.alias}</Table.Td>
                      <Table.Td>
                        <code>{repo.commit ?? '—'}</code>
                      </Table.Td>
                      <Table.Td>{repo.nodes ?? '—'}</Table.Td>
                      <Table.Td>{seconds(repo.duration_ms)}</Table.Td>
                      <Table.Td>
                        <Text size="xs" c={repo.error ? 'red' : 'dimmed'}>
                          {repo.error ?? repo.warning ?? ''}
                        </Text>
                      </Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            )}
          </Stack>
        )}
        {data && (
          <Stack gap="xs">
            <Text fw={600}>Arquivos (knowledge/ e memory/)</Text>
            {data.files.length === 0 ? (
              <Text size="sm" c="dimmed">
                Nenhum arquivo ainda.
              </Text>
            ) : (
              <Stack gap={2}>
                {data.files.map((entry) => (
                  <button
                    key={entry.path}
                    type="button"
                    onClick={() => void openFile(entry.path)}
                    className="flex justify-between gap-3 rounded px-2 py-1 text-left text-sm hover:bg-muted"
                  >
                    <span className="truncate font-mono">{entry.path}</span>
                    <span className="shrink-0 text-muted-foreground">
                      {formatSize(entry.size)} · {formatWhen(entry.modified_at)}
                    </span>
                  </button>
                ))}
              </Stack>
            )}
          </Stack>
        )}
        {file && (
          <Stack gap="xs">
            <Group justify="space-between">
              <Text fw={600} className="font-mono">
                {file.path}
              </Text>
              <Button size="xs" variant="subtle" onClick={() => setFile(null)}>
                Fechar
              </Button>
            </Group>
            {file.truncated && (
              <Text size="xs" c="dimmed">
                Mostrando os primeiros 200 KB de {formatSize(file.size)}.
              </Text>
            )}
            <pre className="max-h-96 overflow-auto whitespace-pre-wrap rounded border border-border bg-muted p-3 text-xs">
              {file.content}
            </pre>
          </Stack>
        )}
      </Stack>
    </Modal>
  )
}
