import { Link } from 'react-router-dom'
import { Burger } from '@/components/ui/legacy'
import type { CurrentUser } from '../../api'
import { ArchivedConversations } from '../../components/chat/ArchivedConversations'
import { ConversationListItem } from '../../components/chat/ConversationListItem'
import styles from '../../components/chat.module.css'
import { CONVERSATION_PAGE_SIZE } from './constants'
import { SidebarUserMenu } from './SidebarUserMenu'
import type { ChatPageState } from './useChatPageState'
import type { useConversationActions } from './useConversationActions'
import type { useConversationList } from './useConversationList'

type ChatSidebarProps = {
  st: ChatPageState
  actions: ReturnType<typeof useConversationActions>
  list: ReturnType<typeof useConversationList>
  currentUser: CurrentUser | null
  isAdminUser: boolean
  isMobile: boolean
  mobileOpened: boolean
  toggleMobile: () => void
  closeMobile: () => void
  sandboxAccessCount: number
}

/** Conversation panel: nova conversa, busca, atalhos, lista agrupada e menu do usuário. */
export function ChatSidebar({
  st, actions, list, currentUser, isAdminUser, isMobile, mobileOpened, toggleMobile, closeMobile,
  sandboxAccessCount,
}: ChatSidebarProps) {
  const {
    conversationsCollapsed, setConversationsCollapsed, conversationSearch, setConversationSearch,
    conversations, mainMode, setMainMode, activeId, archivedRefreshKey, setVisibleConversationCount,
  } = st
  const {
    handleNewChat, handleSelectConversation, handleRenameConversation, handleArchiveConversation,
    handleOpenArchived,
  } = actions
  const { groups, hiddenConversationCount, handleConversationListScroll } = list

  return (
      <>
        <aside
          className={`${styles.sidebar} ${!isMobile && conversationsCollapsed ? styles.sidebarCollapsed : ''} ${isMobile && mobileOpened ? styles.sidebarOpen : ''}`}
          aria-hidden={isMobile && !mobileOpened ? true : undefined}
        >
          <div className={styles.sidebarHead}>
            <div className={styles.sidebarHeadLeft}>
              <img src="/capybara.png" alt="" className={styles.sidebarLogo} />
              <div>
                <div className={styles.sidebarTitle}>CappyCloud</div>
                <div className={styles.sidebarSubtitle}>Workspace</div>
              </div>
            </div>
            {isMobile && (
              <Burger opened={mobileOpened} onClick={toggleMobile} size="sm" color="var(--cc-on-surface-variant)" aria-label="Fechar menu" />
            )}
          </div>

          {/* New session button */}
          <div className={styles.sidebarActions}>
            <button className={styles.newSessionBtn} onClick={handleNewChat}>
              <span className={styles.icon}>add</span>
              <span>Nova conversa</span>
            </button>
            <div className={styles.sessionSearch} role="search">
              <span className={styles.icon}>search</span>
              <input
                value={conversationSearch}
                onChange={(event) => setConversationSearch(event.currentTarget.value)}
                placeholder="Buscar conversas"
                aria-label="Buscar conversas"
              />
              {conversationSearch && (
                <button
                  type="button"
                  className={styles.sessionSearchClear}
                  onClick={() => setConversationSearch('')}
                  title="Limpar busca"
                  aria-label="Limpar busca"
                >
                  <span className={styles.icon}>close</span>
                </button>
              )}
            </div>
          </div>

          <button
            type="button"
            className={styles.collapsedConversationsBtn}
            onClick={() => setConversationsCollapsed(false)}
            title="Expandir conversas"
            aria-label="Expandir conversas"
          >
            <span className={styles.icon}>forum</span>
            <span className={styles.collapsedCount}>{conversations.length}</span>
          </button>

          <div className={styles.sidebarUtility}>
            {isAdminUser && (
              <Link
                to="/admin"
                className={styles.sandboxAccessBtn}
                onClick={closeMobile}
              >
                <span className={`${styles.icon} ${styles.sandboxAccessIcon}`}>dashboard</span>
                <span className={styles.sandboxAccessLabel}>Dashboard admin</span>
              </Link>
            )}
            <button
              type="button"
              className={`${styles.sandboxAccessBtn} ${mainMode === 'sandboxes' ? styles.sandboxAccessBtnActive : ''}`}
              onClick={() => {
                setMainMode('sandboxes')
                closeMobile()
              }}
            >
              <span className={`${styles.icon} ${styles.sandboxAccessIcon}`}>dns</span>
              <span className={styles.sandboxAccessLabel}>Sandboxes & acessos</span>
              <span className={styles.sandboxAccessCount}>
                <span aria-hidden />
                {sandboxAccessCount}
              </span>
            </button>
          </div>

          <div className={styles.sessionList} onScroll={handleConversationListScroll}>
            {groups.length === 0 && (
              <p className={styles.emptyHint}>
                {conversations.length === 0 ? 'Nenhuma conversa ainda.' : 'Nenhuma conversa encontrada.'}
              </p>
            )}
            {groups.map((g) => (
              <section key={g.label}>
                <h3 className={styles.groupLabel}>{g.label}</h3>
                <div className={styles.groupItems}>
                  {g.items.map((c) => (
                    <ConversationListItem
                      key={c.id}
                      conversation={c}
                      active={c.id === activeId}
                      onSelect={() => handleSelectConversation(c.id)}
                      onRename={(title) => handleRenameConversation(c, title)}
                      onArchive={(archived) => handleArchiveConversation(c, archived)}
                    />
                  ))}
                </div>
              </section>
            ))}
            <ArchivedConversations
              activeId={activeId}
              refreshKey={archivedRefreshKey}
              onSelect={handleOpenArchived}
              onRename={handleRenameConversation}
              onUnarchive={(conversation) => handleArchiveConversation(conversation, false)}
            />
            {hiddenConversationCount > 0 && (
              <div className={styles.sessionListFooter}>
                <button
                  type="button"
                  className={styles.loadMoreSessionsBtn}
                  onClick={() => setVisibleConversationCount((count) => count + CONVERSATION_PAGE_SIZE)}
                >
                  <span>Carregar mais</span>
                  <span className={styles.loadMoreCount}>{hiddenConversationCount}</span>
                </button>
              </div>
            )}
          </div>
          <div className={styles.sidebarFooter}>
            <SidebarUserMenu user={currentUser} />
          </div>
        </aside>
        {isMobile && mobileOpened && <div className={styles.mobileBackdrop} onClick={closeMobile} aria-hidden="true" />}
        {isMobile && !mobileOpened && (
          <button type="button" className={styles.mobileMenuBtn} onClick={toggleMobile} aria-label="Abrir menu de conversas">
            <span className={styles.icon}>menu</span>
          </button>
        )}
      </>
  )
}
