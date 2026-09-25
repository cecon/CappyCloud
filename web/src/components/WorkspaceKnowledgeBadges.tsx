import { useCallback, useEffect, useState } from 'react'
import { IconRefresh } from '@tabler/icons-react'
import { Badge, Group, Stack } from '@/components/ui/legacy'
import {
  buildWorkspaceKnowledge,
  fetchWorkspaceKnowledgeSummary,
  getToken,
  type WorkspaceKnowledgeSummary,
} from '../api'
import { RowActionIcon } from './TableActions'
import { graphTone, memoryTone, type Tone } from './workspaceKnowledgeTone'

/** Coluna "Conhecimento" da lista de workspaces: selos do grafo e da memória. */
export function WorkspaceKnowledgeBadges({ workspaceId, onOpen }: { workspaceId: string; onOpen: () => void }) {
  const [summary, setSummary] = useState<WorkspaceKnowledgeSummary | null>(null)
  const [queued, setQueued] = useState(false)

  const load = useCallback(async () => {
    const token = getToken()
    if (!token) return
    try {
      setSummary(await fetchWorkspaceKnowledgeSummary(token, workspaceId))
    } catch {
      setSummary({ graph: { available: false }, memory: { available: false, total: 0, last_at: null, error: null } })
    }
  }, [workspaceId])

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0)
    return () => window.clearTimeout(timer)
  }, [load])

  const running = queued || Boolean(summary?.graph.running || summary?.graph.state === 'running')
  useEffect(() => {
    if (!running) return
    const timer = window.setInterval(() => void load(), 10_000)
    return () => window.clearInterval(timer)
  }, [running, load])

  async function rebuild() {
    const token = getToken()
    if (!token) return
    await buildWorkspaceKnowledge(token, workspaceId).catch(() => undefined)
    setQueued(true)
    window.setTimeout(() => setQueued(false), 30_000)
  }

  if (!summary) return null
  const graph = graphTone(summary.graph)
  const memory = memoryTone(summary.memory)
  const badge = (tone: Tone) => (
    <Badge color={tone.color} variant="light" title={tone.title} className="cursor-pointer whitespace-nowrap" onClick={onOpen}>
      {tone.text}
    </Badge>
  )

  return (
    <Stack gap={4}>
      <Group gap={4} wrap="nowrap">
        {badge(running ? { text: 'Grafo: gerando…', color: 'blue' } : graph)}
        {!running && summary.graph.available !== false && (
          <RowActionIcon label="Atualizar o grafo agora" color="blue" onClick={() => void rebuild()}>
            <IconRefresh size={14} />
          </RowActionIcon>
        )}
      </Group>
      {badge(memory)}
    </Stack>
  )
}
