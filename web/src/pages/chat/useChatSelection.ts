import { useCallback, useMemo, useState } from 'react'
import { DEFAULT_PERMISSION_MODE, type PermissionMode } from '../../api'
import {
  CLAUDE_CLI_DEFAULT_MODEL,
  claudeCliModelFor,
  usesClaudeCli,
} from '../../components/claudeCliModels'
import { CLAUDE_CLI_MODEL_KEY } from './constants'
import { sortModelsForSelect } from './preferences'
import { isSandboxAvailable } from './sandboxStatus'
import type { ChatPageState } from './useChatPageState'

/** Valores derivados da seleção atual (sandbox, workspace, modo de permissão, modelo). */
export function useChatSelection(st: ChatPageState) {
  const {
    models, activeId, conversations, projectWorkspaces, selectedWorkspaceId,
    chosenPermissionMode, sandboxes, selectedSandboxId, workspaces,
  } = st
  const sortedModels = useMemo(() => sortModelsForSelect(models), [models])
  // Sandbox da próxima mensagem: a da conversa aberta ou a do workspace da nova conversa.
  const runtimeSandboxId = activeId
    ? conversations.find((conversation) => conversation.id === activeId)?.sandbox_id
    : projectWorkspaces.find((workspace) => workspace.id === selectedWorkspaceId)?.sandbox_id
  // Modo de planejamento: ligado por workspace; conversa antiga (sem workspace) segue como era.
  const permissionWorkspaceId = activeId
    ? conversations.find((conversation) => conversation.id === activeId)?.workspace_id
    : selectedWorkspaceId
  const planModeEnabled = permissionWorkspaceId
    ? !!projectWorkspaces.find((workspace) => workspace.id === permissionWorkspaceId)?.plan_mode_enabled
    : true
  const permissionMode: PermissionMode =
    chosenPermissionMode === 'plan' && !planModeEnabled ? DEFAULT_PERMISSION_MODE : chosenPermissionMode
  const onClaudeCli = usesClaudeCli(sandboxes.find((sandbox) => sandbox.id === runtimeSandboxId)?.agent_runtime)
  // Escolha do Claude CLI fica separada: não troca o modelo das sandboxes openclaude.
  const [claudeCliModelId, setClaudeCliModelId] = useState(() => {
    try {
      return claudeCliModelFor(localStorage.getItem(CLAUDE_CLI_MODEL_KEY))
    } catch {
      return CLAUDE_CLI_DEFAULT_MODEL
    }
  })
  const chooseClaudeCliModel = useCallback((modelId: string) => {
    const next = claudeCliModelFor(modelId)
    setClaudeCliModelId(next)
    try {
      localStorage.setItem(CLAUDE_CLI_MODEL_KEY, next)
    } catch {
      // Sem storage: vale só nesta aba.
    }
  }, [])
  const availableSandboxes = useMemo(() => sandboxes.filter(isSandboxAvailable), [sandboxes])
  const selectedSandbox = useMemo(
    () => sandboxes.find((sandbox) => sandbox.id === selectedSandboxId) ?? null,
    [sandboxes, selectedSandboxId],
  )
  const selectableWorkspaces = useMemo(() => {
    if (!selectedSandboxId) return workspaces
    return workspaces.filter((workspace) => workspace.sandbox_id === selectedSandboxId)
  }, [selectedSandboxId, workspaces])
  // Conversa nova em workspace que exige o número do chamado.
  const requireTicket =
    !activeId && !!projectWorkspaces.find((workspace) => workspace.id === selectedWorkspaceId)?.require_ticket

  return {
    sortedModels, planModeEnabled, permissionMode, onClaudeCli, claudeCliModelId, chooseClaudeCliModel,
    availableSandboxes, selectedSandbox, selectableWorkspaces, requireTicket,
  }
}

export type ChatSelection = ReturnType<typeof useChatSelection>
