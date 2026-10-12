import { useEffect, useState } from 'react'
import styles from '../../components/chat.module.css'
import type { ActiveChatProps } from './ActiveChat.types'
import { ChatInputBar } from './ChatInputBar'
import { ChatMessageList } from './ChatMessageList'
import { SessionHeader } from './SessionHeader'
import { useChatScroll } from './useChatScroll'
import { useSlashCommands } from './useSlashCommands'

/** Segundos decorridos do turno atual, para o botão de parar. */
function useElapsedSeconds(streaming: boolean): number {
  const [elapsedSecs, setElapsedSecs] = useState(0)

  useEffect(() => {
    if (!streaming) return
    const id = setInterval(() => setElapsedSecs((s) => s + 1), 1000)
    return () => {
      clearInterval(id)
      setElapsedSecs(0)
    }
  }, [streaming])

  return elapsedSecs
}

export function ActiveChat(props: ActiveChatProps) {
  const {
    messages, thoughtSteps, activityTraces, pendingAction, contextProgress, subagentGroups,
    runtimeStates, streaming, token, conversationId, selectedModelId, permissionMode,
  } = props
  const elapsedSecs = useElapsedSeconds(streaming)
  const slash = useSlashCommands(token, conversationId, selectedModelId, permissionMode)
  const scroll = useChatScroll({
    messages, thoughtSteps, activityTraces, pendingAction, contextProgress, subagentGroups,
    runtimeStates, streaming, conversationId,
  })

  return (
    <div className={styles.activeChat}>
      <SessionHeader
        activeEnvSlug={props.activeEnvSlug}
        activeEnvName={props.activeEnvName}
        activeBaseBranch={props.activeBaseBranch}
        activeSandboxName={props.activeSandboxName}
        headBranch={props.headBranch}
        models={props.models}
        selectedModelId={selectedModelId}
        setSelectedModelId={props.setSelectedModelId}
        streaming={streaming}
        diffStats={props.diffStats}
        prLoading={props.prLoading}
        prLinks={props.prLinks}
        prError={props.prError}
        onCreatePr={props.onCreatePr}
      />
      <ChatMessageList {...props} scroll={scroll} />
      <ChatInputBar {...props} slash={slash} elapsedSecs={elapsedSecs} />
    </div>
  )
}
