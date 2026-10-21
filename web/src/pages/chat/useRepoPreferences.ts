import { useEffect } from 'react'
import type { Sandbox } from '../../api'
import { readChatPrefs, updateChatPrefs, validModelId } from './preferences'
import { isSandboxAvailable } from './sandboxStatus'
import type { ChatPageState } from './useChatPageState'

/**
 * Mantém repo/branch/modelo/sandbox coerentes e lembrados por repositório.
 * Os setters vêm do useState (identidade estável); estão nas deps só para o lint.
 */
export function useRepoPreferences(st: ChatPageState, availableSandboxes: Sandbox[]) {
  const {
    selectedSlug, models, setSelectedBranch, setSelectedModelId, sandboxes, setSelectedSandboxId,
    selectedSandboxId, workspaces, setSelectedSlug, selectedBranch, selectedModelId,
  } = st

  useEffect(() => {
    if (!selectedSlug) return
    const prefs = readChatPrefs()
    const branch = prefs.byRepo?.[selectedSlug]?.branch || ''
    setSelectedBranch((prev) => (prev === branch ? prev : branch))
    if (models.length > 0) {
      const modelId = validModelId(models, prefs.byRepo?.[selectedSlug]?.modelId)
      if (modelId) setSelectedModelId((prev) => (prev === modelId ? prev : modelId))
    }
  }, [selectedSlug, models, setSelectedBranch, setSelectedModelId])

  useEffect(() => {
    if (sandboxes.length === 0) {
      setSelectedSandboxId('')
      return
    }
    const currentIsValid = sandboxes.some(
      (sandbox) => sandbox.id === selectedSandboxId && isSandboxAvailable(sandbox),
    )
    if (currentIsValid) return

    const repoSandboxId = workspaces.find((workspace) => workspace.slug === selectedSlug)?.sandbox_id
    const repoSandboxIsValid =
      !!repoSandboxId &&
      sandboxes.some((sandbox) => sandbox.id === repoSandboxId && isSandboxAvailable(sandbox))
    const fallback = availableSandboxes[0]?.id ?? ''
    setSelectedSandboxId(repoSandboxIsValid ? repoSandboxId : fallback)
  }, [availableSandboxes, sandboxes, selectedSandboxId, selectedSlug, workspaces, setSelectedSandboxId])

  useEffect(() => {
    if (!selectedSandboxId || !selectedSlug) return
    const selectedWorkspace = workspaces.find((workspace) => workspace.slug === selectedSlug)
    if (selectedWorkspace?.sandbox_id === selectedSandboxId) return
    setSelectedSlug('')
    setSelectedBranch('')
  }, [selectedSandboxId, selectedSlug, workspaces, setSelectedSlug, setSelectedBranch])

  useEffect(() => {
    if (!selectedSlug) return
    updateChatPrefs((prefs) => {
      const byRepo = { ...(prefs.byRepo || {}) }
      byRepo[selectedSlug] = { ...(byRepo[selectedSlug] || {}), branch: selectedBranch || undefined }
      return { ...prefs, lastRepoSlug: selectedSlug, byRepo }
    })
  }, [selectedSlug, selectedBranch])

  useEffect(() => {
    if (!selectedModelId) return
    updateChatPrefs((prefs) => {
      const byRepo = { ...(prefs.byRepo || {}) }
      if (selectedSlug) {
        byRepo[selectedSlug] = { ...(byRepo[selectedSlug] || {}), modelId: selectedModelId }
      }
      return { ...prefs, lastModelId: selectedModelId, byRepo }
    })
  }, [selectedModelId, selectedSlug])
}
