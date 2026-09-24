import { useCallback, useEffect, useState } from 'react'
import { Badge, Button, Group, Loader, Stack, Text } from '@/components/ui/legacy'
import { errorToUserMessage, fetchWorkspaceMemories, getToken, type WorkspaceMemory } from '../api'

function formatWhen(iso?: string): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' })
}

/** Memórias que o agente gravou no workspace (agentmemory), da mais recente para a mais antiga. */
export function WorkspaceMemoriesSection({ workspaceId }: { workspaceId: string }) {
  const [memories, setMemories] = useState<WorkspaceMemory[] | null>(null)
  const [total, setTotal] = useState(0)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    const token = getToken()
    if (!token) return
    try {
      const data = await fetchWorkspaceMemories(token, workspaceId)
      setMemories(data.memories)
      setTotal(data.total)
      setError(null)
    } catch (err) {
      setError(errorToUserMessage(err))
    }
  }, [workspaceId])

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0)
    return () => window.clearTimeout(timer)
  }, [load])

  return (
    <Stack gap="xs">
      <Group justify="space-between">
        <Group gap="xs">
          <Text fw={600}>Memória do workspace (agentmemory)</Text>
          {memories && (
            <Badge color="gray" variant="light">
              {total}
            </Badge>
          )}
        </Group>
        <Button size="xs" variant="subtle" onClick={() => void load()}>
          Recarregar
        </Button>
      </Group>
      {error && (
        <Text size="sm" c="red">
          {error}
        </Text>
      )}
      {!memories && !error && <Loader size="sm" />}
      {memories && memories.length === 0 && (
        <Text size="sm" c="dimmed">
          Nenhuma memória ainda. O agente grava aqui o que vale para as próximas conversas deste workspace.
        </Text>
      )}
      {memories && memories.length > 0 && (
        <Stack gap="xs" className="max-h-80 overflow-auto">
          {memories.map((memory) => (
            <div key={memory.id} className="rounded border border-border p-2">
              <Group justify="space-between" wrap="nowrap">
                <Badge variant="light">{memory.type}</Badge>
                <Text size="xs" c="dimmed">
                  {formatWhen(memory.updated_at || memory.created_at)}
                </Text>
              </Group>
              <Text size="sm" className="mt-1 whitespace-pre-wrap">
                {memory.content}
              </Text>
              {memory.files.length > 0 && (
                <Text size="xs" c="dimmed" className="mt-1 font-mono">
                  {memory.files.join(', ')}
                </Text>
              )}
            </div>
          ))}
        </Stack>
      )}
    </Stack>
  )
}
