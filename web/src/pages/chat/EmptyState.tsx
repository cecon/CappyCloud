import { useEffect, useMemo, useState } from 'react'
import {
  fetchProjectSuggestions,
  type AccessibleWorkspace,
  type ExecutionProfile,
  type PermissionMode,
  type ProjectSuggestionCard,
  type Workspace,
} from '../../api'
import { AttachmentTray, type TrayItem } from '../../components/AttachmentTray'
import { TicketNumberField } from '../../components/chat/TicketNumberField'
import styles from '../../components/chat.module.css'
import { ExecutionProfileControl, PermissionModeControl } from './AgentControls'
import { isSendableTrayItem } from './attachments'
import { ATTACHMENT_ACCEPT } from './constants'
import { buildProjectQuickActions } from './quickActions'
import { QuickActionCard } from './QuickActionCard'
import { WorkspacePicker } from './WorkspacePicker'

/* ────────────────────────────────────────────────────────────────
   Empty State — command bar premium centralizada
   ──────────────────────────────────────────────────────────────── */
interface EmptyStateProps {
  input: string
  setInput: (v: string) => void
  inputRef: React.RefObject<HTMLTextAreaElement | null>
  onExecute: (text: string) => void
  streaming: boolean
  selectableWorkspaces: Workspace[]
  projectWorkspaces: AccessibleWorkspace[]
  selectedWorkspaceId: string
  setSelectedWorkspaceId: (id: string) => void
  newChatError: string | null
  selectedSlug: string
  requireTicket: boolean
  ticketNumber: string
  setTicketNumber: (value: string) => void
  ticketRef: React.RefObject<HTMLInputElement | null>
  permissionMode: PermissionMode
  setPermissionMode: (mode: PermissionMode) => void
  planModeEnabled: boolean
  executionProfile: ExecutionProfile
  setExecutionProfile: (profile: ExecutionProfile) => void
  permissionWarningRuntimeConfirmed: boolean
  token: string
  trayItems: TrayItem[]
  onPickFiles: (files: FileList | null | undefined) => void
  onPasteFiles: (e: React.ClipboardEvent<HTMLTextAreaElement>) => void
  onRemoveTrayItem: (localId: string) => void
  fileInputRef: React.RefObject<HTMLInputElement | null>
  isDragOver: boolean
  setDragOver: (v: boolean) => void
}

export function EmptyState({
  input, setInput, inputRef, onExecute, streaming,
  selectableWorkspaces,
  projectWorkspaces, selectedWorkspaceId, setSelectedWorkspaceId, newChatError,
  selectedSlug,
  requireTicket, ticketNumber, setTicketNumber, ticketRef,
  token,
  permissionMode, setPermissionMode, planModeEnabled, executionProfile, setExecutionProfile, permissionWarningRuntimeConfirmed,
  trayItems, onPickFiles, onPasteFiles, onRemoveTrayItem, fileInputRef, isDragOver, setDragOver,
}: EmptyStateProps) {
  const [suggestions, setSuggestions] = useState<ProjectSuggestionCard[]>([])
  const [suggestionsSlug, setSuggestionsSlug] = useState('')
  const [ticketTouched, setTicketTouched] = useState(false)
  // Workspace que exige chamado: o cursor já começa no campo do número.
  useEffect(() => {
    if (requireTicket && !ticketRef.current?.value) ticketRef.current?.focus()
  }, [requireTicket, ticketRef])
  const selectedWorkspace = useMemo(
    () => selectableWorkspaces.find((workspace) => workspace.slug === selectedSlug) ?? null,
    [selectableWorkspaces, selectedSlug],
  )

  // auto-clone trata o caso de repo não clonado
  const hasSendableAttachment = trayItems.some(isSendableTrayItem)
  const hasUploadInProgress = trayItems.some((item) => item.kind === 'uploading')
  const chosenWorkspace = projectWorkspaces.find((workspace) => workspace.id === selectedWorkspaceId) ?? null
  const canExecute =
    !!chosenWorkspace?.ready &&
    (!requireTicket || !!ticketNumber.trim()) &&
    (!!input.trim() || hasSendableAttachment) &&
    !hasUploadInProgress &&
    !streaming

  useEffect(() => {
    if (!selectedSlug) {
      return
    }
    let cancelled = false
    fetchProjectSuggestions(token, selectedSlug, 4)
      .then((result) => {
        if (cancelled) return
        setSuggestions(result.cards)
        setSuggestionsSlug(selectedSlug)
      })
      .catch(() => {
        if (cancelled) return
        setSuggestions([])
        setSuggestionsSlug(selectedSlug)
      })
    return () => { cancelled = true }
  }, [selectedSlug, token])

  function handleKey(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey && !streaming) {
      e.preventDefault()
      // Falta o chamado: Enter leva ao campo em vez de enviar.
      if (requireTicket && !ticketNumber.trim()) {
        setTicketTouched(true)
        ticketRef.current?.focus()
        return
      }
      if (canExecute) onExecute(input)
    }
  }

  const quickActions = buildProjectQuickActions({
    repoName: selectedWorkspace?.name || selectedSlug || 'seu projeto',
    suggestions: selectedSlug && suggestionsSlug === selectedSlug ? suggestions : [],
    hasSelection: !!selectedSlug,
  })

  return (
    <div className={styles.emptyState}>
      <section className={styles.welcomePanel}>
        <div className={styles.mascotWrapper}>
          <img src="/capybara.png" alt="CappyCloud" className={styles.mascot} />
          <div className={styles.mascotGlow} />
        </div>
        <div className={styles.welcomeCopy}>
          <h1 className={styles.welcomeTitle}>
            O que devemos criar em {selectedWorkspace?.name || 'CappyCloud'}?
          </h1>
          <p className={styles.welcomeText}>
            {selectedSlug
              ? 'Sugestões ajustadas ao projeto selecionado e recalibradas conforme o uso.'
              : 'Escolha um projeto para receber sugestões específicas antes de começar.'}
          </p>
        </div>
      </section>

      <div className={styles.quickActions}>
        {quickActions.map((action) => (
          <QuickActionCard
            key={action.key}
            icon={action.icon}
            iconColor={action.iconColor}
            title={action.title}
            desc={action.desc}
            disabled={action.disabled}
            onPick={action.disabled ? undefined : setInput}
          />
        ))}
      </div>

      <div
        className={`${styles.commandBarWrapper} ${isDragOver ? styles.commandBarWrapperDragOver : ''}`}
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
        <div className={styles.commandBarGlow} />
        <div className={styles.commandBar}>
          <div className={styles.commandBarInner}>
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
            <AttachmentTray
              items={trayItems}
              token={token}
              conversationId={null}
              onRemove={onRemoveTrayItem}
            />
            {newChatError && (
              <div className={styles.chatStateCardError} role="alert" style={{ padding: '0.5rem 0.75rem', fontSize: '0.8rem' }}>
                {newChatError}
              </div>
            )}
            {requireTicket && (
              <TicketNumberField
                value={ticketNumber}
                onChange={setTicketNumber}
                onDone={() => inputRef.current?.focus()}
                inputRef={ticketRef}
                missing={ticketTouched && !ticketNumber.trim()}
                disabled={streaming}
              />
            )}
            <div className={styles.commandInputRow}>
              <span className={`${styles.icon} ${styles.boltIcon}`}>bolt</span>
              <textarea
                ref={inputRef}
                className={styles.commandTextarea}
                placeholder={
                  chosenWorkspace?.ready
                    ? 'Pergunte algo ao agente... (Enter para enviar)'
                    : 'Pergunte algo ao agente...'
                }
                rows={2}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onPaste={onPasteFiles}
                onKeyDown={handleKey}
                disabled={streaming}
              />
            </div>

            <div className={styles.commandToolbar}>
              <div className={styles.commandToolbarLeft}>
                <button
                  className={styles.toolbarBtn}
                  title="Anexar imagem ou arquivo"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={streaming}
                  type="button"
                >
                  <span className={styles.icon}>attachment</span>
                </button>
                <WorkspacePicker
                  projectWorkspaces={projectWorkspaces}
                  selectedWorkspaceId={selectedWorkspaceId}
                  setSelectedWorkspaceId={setSelectedWorkspaceId}
                  chosenWorkspace={chosenWorkspace}
                />
                <PermissionModeControl
                  value={permissionMode}
                  onChange={setPermissionMode}
                  planModeEnabled={planModeEnabled}
                  disabled={streaming}
                  runtimeConfirmed={permissionWarningRuntimeConfirmed}
                />
                <ExecutionProfileControl
                  value={executionProfile}
                  onChange={setExecutionProfile}
                  disabled={streaming}
                />
              </div>

              <div className={styles.commandToolbarRight}>
                <button
                  className={styles.executeBtn}
                  onClick={() => canExecute && onExecute(input)}
                  disabled={!canExecute}
                  title={
                    !chosenWorkspace ? 'Selecione um workspace' :
                    !chosenWorkspace.ready ? 'Workspace ainda sincronizando' :
                    hasUploadInProgress ? 'Aguarde os anexos terminarem o envio…' :
                    !input.trim() && !hasSendableAttachment ? 'Digite uma mensagem ou cole um print' : undefined
                  }
                >
                  <span>Executar</span>
                  <span className={styles.icon}>keyboard_return</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <p className={styles.emptyHint}>
        Você está numa cópia isolada — nada do que testar aqui afeta os outros usuários.
      </p>
    </div>
  )
}
