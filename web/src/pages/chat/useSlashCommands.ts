import { useCallback, useEffect, useState } from 'react'
import {
  errorToUserMessage,
  executeSlashCommand,
  listSlashCommands,
  type PermissionMode,
  type SlashCommand,
} from '../../api'
import { slashCommandQuery, shouldOpenSlashCommands } from '../../components/chat/SlashCommandMenu.utils'

/** Catálogo, abertura e execução dos slash commands da conversa ativa. */
export function useSlashCommands(
  token: string,
  conversationId: string,
  selectedModelId: string,
  permissionMode: PermissionMode,
) {
  const [slashCommands, setSlashCommands] = useState<SlashCommand[]>([])
  const [slashOpen, setSlashOpen] = useState(false)
  const [slashQuery, setSlashQuery] = useState('')
  const [commandNotice, setCommandNotice] = useState<string | null>(null)
  const [confirmCommand, setConfirmCommand] = useState<{
    command: SlashCommand
    message: string
    confirmLabel: string
    cancelLabel: string
  } | null>(null)

  useEffect(() => {
    queueMicrotask(() => {
      setSlashOpen(false)
      setSlashQuery('')
      setSlashCommands([])
      setCommandNotice(null)
      setConfirmCommand(null)
    })
  }, [conversationId, selectedModelId, permissionMode])

  const openSlashCommands = useCallback((draft: string, caret: number) => {
    if (!shouldOpenSlashCommands(draft, caret) && !slashOpen) return
    setSlashQuery(slashCommandQuery(draft, caret))
    setSlashOpen(true)
    if (slashCommands.length === 0) {
      listSlashCommands(token, conversationId)
        .then((catalog) => setSlashCommands(catalog.commands))
        .catch(() => setCommandNotice('Nao foi possivel carregar comandos agora.'))
    }
  }, [conversationId, slashCommands.length, slashOpen, token])

  const runSlashCommand = useCallback(async (command: SlashCommand, confirmed = false) => {
    const unavailable =
      command.execution_mode === 'unavailable' ||
      command.availability.state === 'unavailable' ||
      command.availability.state === 'blocked'
    if (unavailable) {
      setCommandNotice(command.availability.reason || 'Comando indisponivel nesta conversa.')
      return
    }
    try {
      const response = await executeSlashCommand(token, conversationId, {
        command: command.name,
        confirmed,
        client_request_id: crypto.randomUUID(),
      })
      if (response.status === 'needs_confirmation' && response.confirmation) {
        setConfirmCommand({
          command,
          message: response.confirmation.message,
          confirmLabel: response.confirmation.confirm_label,
          cancelLabel: response.confirmation.cancel_label,
        })
        return
      }
      setCommandNotice(response.message || 'Comando enviado.')
      setConfirmCommand(null)
      setSlashOpen(false)
    } catch (error) {
      setCommandNotice(errorToUserMessage(error))
    }
  }, [conversationId, token])

  const pickSlashCommand = useCallback((command: SlashCommand) => {
    setSlashOpen(false)
    const unavailable =
      command.execution_mode === 'unavailable' ||
      command.availability.state === 'unavailable' ||
      command.availability.state === 'blocked'
    if (unavailable) {
      void runSlashCommand(command)
      return
    }
    if (command.requires_confirmation) {
      setConfirmCommand({
        command,
        message: command.confirmation_reason || 'Confirme a execucao do comando.',
        confirmLabel: 'Executar',
        cancelLabel: 'Cancelar',
      })
      return
    }
    void runSlashCommand(command)
  }, [runSlashCommand])

  return {
    slashCommands,
    slashOpen,
    setSlashOpen,
    slashQuery,
    commandNotice,
    confirmCommand,
    setConfirmCommand,
    openSlashCommands,
    runSlashCommand,
    pickSlashCommand,
  }
}

export type SlashCommandsState = ReturnType<typeof useSlashCommands>
