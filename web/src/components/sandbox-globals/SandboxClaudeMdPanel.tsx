import { useEffect, useState } from 'react'
import { Alert, Button, Group, Stack, Text, Textarea } from '@/components/ui/legacy'
import {
  bootAdminSandbox,
  errorToUserMessage,
  getToken,
  type Sandbox,
  updateAdminSandbox,
} from '../../api'

type Props = {
  sandbox: Sandbox
  onUpdated: (sandbox: Sandbox) => void
}

export function SandboxClaudeMdPanel({ sandbox, onUpdated }: Props) {
  const [draft, setDraft] = useState(sandbox.claude_md ?? '')
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    setDraft(sandbox.claude_md ?? '')
    setError(null)
    setSaved(false)
  }, [sandbox.id, sandbox.claude_md])

  async function saveAndApply() {
    const token = getToken()
    if (!token) return
    setSaving(true)
    setError(null)
    setSaved(false)
    try {
      const savedSandbox = await updateAdminSandbox(token, sandbox.id, { claude_md: draft })
      const configured = await bootAdminSandbox(token, sandbox.id)
      onUpdated({ ...configured, claude_md: savedSandbox.claude_md })
      setSaved(true)
    } catch (err) {
      setError(errorToUserMessage(err))
    } finally {
      setSaving(false)
    }
  }

  return (
    <Stack gap="md">
      {error && (
        <Alert color="red" title="Não foi possível salvar">
          {error}
        </Alert>
      )}
      {saved && (
        <Alert color="green" title="CLAUDE.md aplicado">
          O arquivo foi salvo no cadastro e materializado na sandbox.
        </Alert>
      )}
      <Text size="sm" c="dimmed">
        Instruções globais do terminal headless desta sandbox. Novas sessões recebem este arquivo
        na raiz do worktree.
      </Text>
      <Textarea
        aria-label="Conteúdo do CLAUDE.md"
        value={draft}
        onChange={(event) => setDraft(event.currentTarget.value)}
        minRows={24}
        spellCheck={false}
        style={{ fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace' }}
      />
      <Group justify="flex-end">
        <Button onClick={saveAndApply} loading={saving} disabled={saving}>
          Salvar e aplicar
        </Button>
      </Group>
    </Stack>
  )
}
