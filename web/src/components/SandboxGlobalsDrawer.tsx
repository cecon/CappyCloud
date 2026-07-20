import { Drawer, Stack, Tabs, Text, Title } from '@/components/ui/legacy'
import type { Sandbox } from '../api'
import { SandboxAgentsPanel } from './sandbox-globals/SandboxAgentsPanel'
import { SandboxClaudeMdPanel } from './sandbox-globals/SandboxClaudeMdPanel'
import { SandboxMcpsPanel } from './sandbox-globals/SandboxMcpsPanel'
import { SandboxSkillsPanel } from './sandbox-globals/SandboxSkillsPanel'

type Props = {
  sandbox: Sandbox | null
  onClose: () => void
  onUpdated: (sandbox: Sandbox) => void
}

/**
 * Drawer único com 3 tabs (MCPs / Skills / Agents) — todos materializados em
 * ``~/.claude/`` dentro do container da sandbox ao boot (ADR-004 §5-6).
 */
export function SandboxGlobalsDrawer({ sandbox, onClose, onUpdated }: Props) {
  return (
    <Drawer
      opened={sandbox !== null}
      onClose={onClose}
      position="right"
      size="xl"
      title={
        sandbox ? (
          <Stack gap={2}>
            <Title order={4}>{sandbox.name} · periféricos</Title>
            <Text size="xs" c="dimmed">
              CLAUDE.md, MCPs, skills globais e subagents materializados em ~/.claude.
            </Text>
          </Stack>
        ) : null
      }
    >
      {sandbox && (
        <Tabs defaultValue="claude" keepMounted={false}>
          <Tabs.List>
            <Tabs.Tab value="claude">CLAUDE.md</Tabs.Tab>
            <Tabs.Tab value="mcps">MCPs</Tabs.Tab>
            <Tabs.Tab value="skills">Skills</Tabs.Tab>
            <Tabs.Tab value="agents">Subagents</Tabs.Tab>
          </Tabs.List>
          <Tabs.Panel value="claude" pt="md">
            <SandboxClaudeMdPanel sandbox={sandbox} onUpdated={onUpdated} />
          </Tabs.Panel>
          <Tabs.Panel value="mcps" pt="md">
            <SandboxMcpsPanel sandbox={sandbox} />
          </Tabs.Panel>
          <Tabs.Panel value="skills" pt="md">
            <SandboxSkillsPanel sandbox={sandbox} canManage={false} />
          </Tabs.Panel>
          <Tabs.Panel value="agents" pt="md">
            <SandboxAgentsPanel sandbox={sandbox} />
          </Tabs.Panel>
        </Tabs>
      )}
    </Drawer>
  )
}
