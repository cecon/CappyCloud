import { AttachmentTray } from '../../components/AttachmentTray'
import { CommandConfirmation } from '../../components/chat/CommandConfirmation'
import { SlashCommandMenu } from '../../components/chat/SlashCommandMenu'
import styles from '../../components/chat.module.css'
import type { ActiveChatProps } from './ActiveChat.types'
import { ExecutionProfileControl, PermissionModeControl } from './AgentControls'
import { isSendableTrayItem } from './attachments'
import { ATTACHMENT_ACCEPT } from './constants'
import type { SlashCommandsState } from './useSlashCommands'
import { UsagePills } from './UsagePills'

type ChatInputBarProps = Pick<
  ActiveChatProps,
  | 'streaming' | 'input' | 'setInput' | 'inputRef' | 'onSend' | 'onStop' | 'pendingAction'
  | 'token' | 'conversationId' | 'permissionMode' | 'setPermissionMode' | 'planModeEnabled'
  | 'executionProfile' | 'setExecutionProfile' | 'permissionWarningRuntimeConfirmed'
  | 'convUsage' | 'liveUsage' | 'trayItems' | 'onPickFiles' | 'onPasteFiles' | 'onRemoveTrayItem'
  | 'fileInputRef' | 'isDragOver' | 'setDragOver'
> & { slash: SlashCommandsState; elapsedSecs: number }

/** Compact input bar: anexos, slash commands, envio e barra de contexto. */
export function ChatInputBar({
  streaming, input, setInput, inputRef, onSend, onStop, pendingAction, token, conversationId,
  permissionMode, setPermissionMode, planModeEnabled, executionProfile, setExecutionProfile,
  permissionWarningRuntimeConfirmed, convUsage, liveUsage,
  trayItems, onPickFiles, onPasteFiles, onRemoveTrayItem, fileInputRef, isDragOver, setDragOver,
  slash, elapsedSecs,
}: ChatInputBarProps) {
  const {
    slashOpen, setSlashOpen, slashCommands, slashQuery, commandNotice, confirmCommand,
    setConfirmCommand, openSlashCommands, runSlashCommand, pickSlashCommand,
  } = slash
  const hasSendableAttachment = trayItems.some(isSendableTrayItem)
  const hasUploadInProgress = trayItems.some((item) => item.kind === 'uploading')

  return (
      <div
        className={`${styles.chatInputBar} ${isDragOver ? styles.chatInputBarDragOver : ''}`}
        onDragOver={(e) => {
          if (!e.dataTransfer?.types?.includes('Files')) return
          e.preventDefault()
          setDragOver(true)
        }}
        onDragLeave={(e) => {
          if (e.currentTarget === e.target) setDragOver(false)
        }}
        onDrop={(e) => {
          e.preventDefault()
          setDragOver(false)
          onPickFiles(e.dataTransfer?.files)
        }}
      >
        <div className={styles.chatInputBarShell}>
          <AttachmentTray
            items={trayItems}
            token={token}
            conversationId={conversationId}
            onRemove={onRemoveTrayItem}
          />
          <div className={styles.chatInputWrapper}>
          <input
            ref={fileInputRef}
            type="file"
            accept={ATTACHMENT_ACCEPT}
            multiple
            style={{ display: 'none' }}
            onChange={(e) => {
              onPickFiles(e.target.files)
              if (e.target) e.target.value = ''
            }}
          />
          <button
            type="button"
            className={styles.attachBtn}
            onClick={() => fileInputRef.current?.click()}
            disabled={streaming}
            title="Anexar imagem ou arquivo da conversa"
            aria-label="Anexar imagem ou arquivo"
          >
            <span className={styles.icon}>attachment</span>
          </button>
          {slashOpen && (
            <div className={styles.slashCommandOverlay}>
              <SlashCommandMenu
                commands={slashCommands}
                query={slashQuery}
                onPick={pickSlashCommand}
                onDismiss={() => setSlashOpen(false)}
              />
            </div>
          )}
          <textarea
            ref={inputRef}
            className={styles.chatTextarea}
            placeholder={
              isDragOver
                ? 'Solte para anexar à conversa…'
                : 'Mensagem ao agente… (Enter para enviar, cole imagens com Ctrl+V)'
            }
            rows={2}
            value={input}
            onChange={(e) => {
              const next = e.target.value
              setInput(next)
              openSlashCommands(next, e.target.selectionStart ?? next.length)
            }}
            onPaste={onPasteFiles}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey && !streaming) {
                e.preventDefault()
                onSend()
              }
            }}
            disabled={streaming && !pendingAction}
          />
          {streaming ? (
            <button className={styles.stopBtn} onClick={onStop} title="Parar agente">
              <span className={styles.icon}>stop</span>
              <span className={styles.stopBtnTimer}>{elapsedSecs}s</span>
            </button>
          ) : (
          <button
            className={styles.sendBtn}
            onClick={onSend}
            disabled={
              (!input.trim() && !pendingAction && !hasSendableAttachment) ||
              (streaming && !pendingAction) ||
              hasUploadInProgress
            }
            title={
              hasUploadInProgress
                ? 'Aguarde os anexos terminarem o envio…'
                : !input.trim() && !pendingAction && hasSendableAttachment
                  ? 'Enviar imagem anexada'
                : undefined
            }
          >
            <span className={styles.icon}>keyboard_return</span>
          </button>
          )}
          </div>

          {confirmCommand && (
            <div className={styles.commandFeedback}>
              <CommandConfirmation
                message={confirmCommand.message}
                confirmLabel={confirmCommand.confirmLabel}
                cancelLabel={confirmCommand.cancelLabel}
                onCancel={() => setConfirmCommand(null)}
                onConfirm={() => void runSlashCommand(confirmCommand.command, true)}
              />
            </div>
          )}
          {commandNotice && (
            <div className={styles.commandFeedback} role="status">
              {commandNotice}
            </div>
          )}

          <div className={styles.chatContextBar}>
            <PermissionModeControl
              value={permissionMode}
              onChange={setPermissionMode}
              planModeEnabled={planModeEnabled}
              disabled={streaming}
              runtimeConfirmed={permissionWarningRuntimeConfirmed}
              compact
            />
            <ExecutionProfileControl
              value={executionProfile}
              onChange={setExecutionProfile}
              disabled={streaming}
              compact
            />
            <UsagePills convUsage={convUsage} liveUsage={liveUsage} />
          </div>
        </div>
      </div>
  )
}
