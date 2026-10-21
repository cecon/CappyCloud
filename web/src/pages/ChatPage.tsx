import { useDisclosure } from '@/components/ui/legacy'
import { getToken } from '../api'
import { CLAUDE_CLI_MODELS } from '../components/claudeCliModels'
import { ThinkingIndicator } from '../components/ThinkingIndicator'
import { useCurrentUser } from '../hooks/useCurrentUser'
import { useIsMobile } from '../hooks/useIsMobile'
import styles from '../components/chat.module.css'
import { ActiveChat } from './chat/ActiveChat'
import { ChatSidebar } from './chat/ChatSidebar'
import { EmptyState } from './chat/EmptyState'
import { streamIdleMsSince } from './chat/formatting'
import { SandboxAccessView } from './chat/SandboxAccessView'
import { isSandboxAvailable } from './chat/sandboxStatus'
import { useAttachmentTray } from './chat/useAttachmentTray'
import { useChatBootstrap } from './chat/useChatBootstrap'
import { useChatEffects } from './chat/useChatEffects'
import { useChatPageState } from './chat/useChatPageState'
import { useChatSelection } from './chat/useChatSelection'
import { useConversationActions } from './chat/useConversationActions'
import { useConversationList } from './chat/useConversationList'
import { useConversationMessages } from './chat/useConversationMessages'
import { usePermissionSettings } from './chat/usePermissionSettings'
import { useRepoPreferences } from './chat/useRepoPreferences'
import { useSendMessage } from './chat/useSendMessage'
import { useStartConversation } from './chat/useStartConversation'

/**
 * UI principal: layout IDE estilo "The Silent Architect".
 * Estado vazio → command bar premium centralizada.
 * Estado ativo  → lista de mensagens + input compacto.
 */
export function ChatPage() {
  const token = getToken()!
  const currentUserState = useCurrentUser()
  const currentUser = currentUserState.status === 'ready' ? currentUserState.user : null
  const isAdminUser = currentUser?.role === 'admin'
  const [mobileOpened, { toggle: toggleMobile, close: closeMobile }] = useDisclosure()
  // Celular: a barra lateral vira gaveta (abre pelo botão ☰, fecha ao escolher).
  const isMobile = useIsMobile()

  const st = useChatPageState()
  const selection = useChatSelection(st)
  const {
    sortedModels, planModeEnabled, permissionMode, onClaudeCli, claudeCliModelId, chooseClaudeCliModel,
    selectedSandbox, selectableWorkspaces, requireTicket,
  } = selection
  const { setPermissionMode, setExecutionProfile } = usePermissionSettings(st, token)
  const tray = useAttachmentTray({
    token,
    activeId: st.activeId,
    models: st.models,
    onClaudeCli,
    selectedModelId: st.selectedModelId,
    setSelectedModelId: st.setSelectedModelId,
  })

  useChatEffects(st, token)
  useChatBootstrap(st, token)
  useRepoPreferences(st, selection.availableSandboxes)
  const loadActivityHistory = useConversationMessages(st, token)
  const actions = useConversationActions(st, tray, token, closeMobile)
  const handleNewChatWithMessage = useStartConversation({ st, selection, tray, token, loadActivityHistory })
  const { handleSend, handleActionReply } = useSendMessage({ st, selection, tray, token, loadActivityHistory })

  const {
    conversations, activeId, mainMode, setMainMode, messages, streaming, sandboxes, workspaces,
    projectWorkspaces, thoughtSteps, pendingAction, streamActivityAt, streamStartedAt, streamElapsedMs,
  } = st
  const activeConv = conversations.find((c) => c.id === activeId)
  const activeEnvSlug = activeConv?.repos?.[0]?.slug ?? null
  const activeProjectWorkspace = activeConv?.workspace_id
    ? projectWorkspaces.find((workspace) => workspace.id === activeConv.workspace_id) ?? null
    : null
  const activeSandboxName =
    sandboxes.find((sandbox) => sandbox.id === activeConv?.sandbox_id)?.name ??
    selectedSandbox?.name ??
    null
  const showThinking =
    streaming &&
    thoughtSteps.length === 0 &&
    !pendingAction

  const list = useConversationList(st)
  const activeSandboxCount = sandboxes.filter(isSandboxAvailable).length
  const sandboxAccessCount = activeSandboxCount
  const streamIdleMs = streamIdleMsSince(streaming, streamActivityAt)

  if (st.loading) {
    return (
      <div className={styles.loadingWrapper}>
        <ThinkingIndicator />
      </div>
    )
  }

  const attachmentProps = {
    trayItems: tray.trayItems,
    onPickFiles: tray.handleFileSelection,
    onPasteFiles: tray.handlePaste,
    onRemoveTrayItem: tray.removeTrayItem,
    fileInputRef: tray.fileInputRef,
    isDragOver: tray.isDragOver,
    setDragOver: tray.setIsDragOver,
  }
  const controlProps = {
    permissionMode,
    setPermissionMode,
    planModeEnabled,
    executionProfile: st.executionProfile,
    setExecutionProfile,
    permissionWarningRuntimeConfirmed: st.permissionWarningRuntimeConfirmed,
    token,
  }

  return (
    <div className={styles.shell}>
      <div className={styles.body}>
        {/* ── Conversation panel ───────────────────────────────── */}
        <ChatSidebar
          st={st}
          actions={actions}
          list={list}
          currentUser={currentUser}
          isAdminUser={isAdminUser}
          isMobile={isMobile}
          mobileOpened={mobileOpened}
          toggleMobile={toggleMobile}
          closeMobile={closeMobile}
          sandboxAccessCount={sandboxAccessCount}
        />

        {/* ── Main ─────────────────────────────────────────────── */}
        <main className={styles.main}>
          {mainMode === 'sandboxes' ? (
            <SandboxAccessView
              sandboxes={sandboxes}
              workspaces={workspaces}
              conversations={conversations}
              onBackToChat={() => setMainMode('chat')}
            />
          ) : !activeId ? (
          <EmptyState
            input={st.input}
            setInput={st.setInput}
            inputRef={st.inputRef}
            onExecute={(text) => handleNewChatWithMessage(text)}
            streaming={streaming}
            selectableWorkspaces={selectableWorkspaces}
            projectWorkspaces={projectWorkspaces}
            selectedWorkspaceId={st.selectedWorkspaceId}
            setSelectedWorkspaceId={st.setSelectedWorkspaceId}
            newChatError={st.newChatError}
            selectedSlug={st.selectedSlug}
            requireTicket={requireTicket}
            ticketNumber={st.ticketNumber}
            setTicketNumber={st.setTicketNumber}
            ticketRef={st.ticketRef}
            {...controlProps}
            {...attachmentProps}
          />
          ) : (
            <ActiveChat
              messages={messages}
              messagesLoading={st.messagesLoading}
              messagesError={st.messagesError}
              sessionProgressAnchor={st.sessionProgressAnchor}
              thoughtSteps={thoughtSteps}
              activityTraces={st.activityTraces}
              streamElapsedMs={streamElapsedMs}
              streamNowMs={streamStartedAt !== null ? streamStartedAt + streamElapsedMs : 0}
              streamIdleMs={streamIdleMs}
              pendingAction={pendingAction}
              contextProgress={st.contextProgress}
              subagentGroups={st.subagentGroups}
              runtimeStates={st.runtimeStates}
              streamToolStats={st.streamToolStats}
              showThinking={showThinking}
              streaming={streaming}
              input={st.input}
              setInput={st.setInput}
              inputRef={st.inputRef}
              onSend={() => handleSend()}
              onStop={actions.handleStop}
              onActionReply={handleActionReply}
              activeEnvSlug={activeEnvSlug}
              activeEnvName={
                activeProjectWorkspace
                  ? `${activeProjectWorkspace.name} · ${activeProjectWorkspace.repositories.length} repositórios${
                      activeConv?.ticket_number ? ` · Chamado ${activeConv.ticket_number}` : ''
                    }`
                  : workspaces.find(w => w.slug === activeEnvSlug)?.name ?? activeEnvSlug ?? workspaces[0]?.name ?? null
              }
              activeBaseBranch={activeConv?.repos?.[0]?.base_branch ?? null}
              activeSandboxName={activeSandboxName}
              sandboxAccessCount={sandboxAccessCount}
              diffStats={st.diffStats}
              prLoading={st.prLoading}
              prLinks={st.prLinks}
              prError={st.prError}
              headBranch={st.headBranch}
              onCreatePr={actions.handleCreatePr}
              activeTitle={activeConv?.title ?? 'Conversa'}
              conversationId={activeId!}
              models={onClaudeCli ? CLAUDE_CLI_MODELS : sortedModels}
              selectedModelId={onClaudeCli ? claudeCliModelId : st.selectedModelId}
              setSelectedModelId={onClaudeCli ? chooseClaudeCliModel : st.setSelectedModelId}
              convUsage={st.convUsage}
              liveUsage={st.liveUsage}
              {...controlProps}
              {...attachmentProps}
            />
          )}
        </main>
      </div>
    </div>
  )
}
