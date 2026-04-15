import { useEffect, useRef, useState } from 'react'
import {
  AppShell,
  Burger,
  Button,
  Group,
  ScrollArea,
  Stack,
  Text,
  Textarea,
  Title,
  UnstyledButton,
} from '@mantine/core'
import { useDisclosure } from '@mantine/hooks'
import {
  createConversation,
  fetchConversations,
  fetchMessages,
  getToken,
  setToken,
  streamAssistantReply,
  type ActionRequiredEvent,
  type ChatMessage,
  type Conversation,
} from '../api'
import { ActionRequiredCard } from '../components/ActionRequiredCard'
import { ThinkingIndicator } from '../components/ThinkingIndicator'
import { ToolCallCard, type ToolCallState } from '../components/ToolCallCard'
import styles from '../components/chat.module.css'

/**
 * UI principal: lista de conversas e chat com streaming do agente.
 * Suporta tool calls animados, HITL (confirmação/opções), e animações de digitação.
 */
export function ChatPage() {
  const token = getToken()!
  const [mobileOpened, { toggle: toggleMobile }] = useDisclosure()

  const [conversations, setConversations] = useState<Conversation[]>([])
  const [activeId, setActiveId] = useState<string | null>(null)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [loading, setLoading] = useState(true)

  // Streaming state
  const [pendingText, setPendingText] = useState('')
  const [pendingTools, setPendingTools] = useState<ToolCallState[]>([])
  const [pendingAction, setPendingAction] = useState<ActionRequiredEvent | null>(null)

  const scrollRef = useRef<HTMLDivElement>(null)

  // Auto-scroll to bottom when messages or pending state change
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
    }
  }, [messages, pendingText, pendingTools, pendingAction, streaming])

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const list = await fetchConversations(token)
        if (cancelled) return
        setConversations(list)
        if (list.length > 0) {
          setActiveId((prev) => prev ?? list[0].id)
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [token])

  useEffect(() => {
    if (!activeId) return
    let cancelled = false
    ;(async () => {
      const msgs = await fetchMessages(token, activeId)
      if (!cancelled) setMessages(msgs)
    })()
    return () => {
      cancelled = true
    }
  }, [activeId, token])

  async function handleNewChat() {
    const c = await createConversation(token)
    setConversations((prev) => [c, ...prev])
    setActiveId(c.id)
    setMessages([])
  }

  async function handleSend(textOverride?: string) {
    const text = (textOverride ?? input).trim()
    if (!text || !activeId || streaming) return

    if (!textOverride) setInput('')
    setStreaming(true)
    setPendingText('')
    setPendingTools([])
    setPendingAction(null)

    const userMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content: text,
      created_at: new Date().toISOString(),
    }
    setMessages((m) => [...m, userMsg])

    try {
      await streamAssistantReply(token, activeId, text, {
        onText(accumulated) {
          setPendingText(accumulated)
        },
        onToolStart(tool) {
          setPendingTools((prev) => [
            ...prev,
            { id: tool.id, name: tool.name, input: tool.input, done: false },
          ])
        },
        onToolResult(result) {
          setPendingTools((prev) =>
            prev.map((t) =>
              t.id === result.id
                ? { ...t, output: result.output, isError: result.is_error, done: true }
                : t
            )
          )
        },
        onActionRequired(action) {
          setPendingAction(action)
        },
        onError(message) {
          setMessages((m) => [
            ...m,
            {
              id: crypto.randomUUID(),
              role: 'assistant',
              content: `**Erro:** ${message}`,
              created_at: new Date().toISOString(),
            },
          ])
        },
      })

      // Stream ended — if no pending action, reload messages from DB
      if (!pendingAction) {
        setPendingText('')
        setPendingTools([])
        const msgs = await fetchMessages(token, activeId)
        setMessages(msgs)
      }
    } catch (e) {
      setMessages((m) => [
        ...m,
        {
          id: crypto.randomUUID(),
          role: 'assistant',
          content: `**Erro:** ${e instanceof Error ? e.message : String(e)}`,
          created_at: new Date().toISOString(),
        },
      ])
    } finally {
      setStreaming(false)
    }
  }

  function handleActionReply(reply: string) {
    // Send as a normal message — backend routes to send_input() if pending action exists
    handleSend(reply)
  }

  function logout() {
    setToken(null)
    window.location.reload()
  }

  const activeTitle = conversations.find((c) => c.id === activeId)?.title ?? 'Conversa'
  const showThinking = streaming && !pendingText && pendingTools.every((t) => t.done) && !pendingAction

  if (loading) {
    return (
      <Group justify="center" p="xl">
        <ThinkingIndicator />
      </Group>
    )
  }

  return (
    <AppShell
      header={{ height: 56 }}
      navbar={{
        width: 280,
        breakpoint: 'sm',
        collapsed: { mobile: !mobileOpened },
      }}
      padding="md"
    >
      <AppShell.Header>
        <Group h="100%" px="md" justify="space-between">
          <Group>
            <Burger opened={mobileOpened} onClick={toggleMobile} hiddenFrom="sm" size="sm" />
            <Title order={4}>CappyCloud</Title>
          </Group>
          <Button variant="subtle" onClick={logout}>
            Sair
          </Button>
        </Group>
      </AppShell.Header>

      <AppShell.Navbar p="md">
        <Button fullWidth mb="sm" onClick={handleNewChat}>
          Nova conversa
        </Button>
        <ScrollArea h="calc(100vh - 120px)">
          <Stack gap={4}>
            {conversations.map((c) => (
              <UnstyledButton
                key={c.id}
                onClick={() => setActiveId(c.id)}
                p="xs"
                style={{
                  borderRadius: 8,
                  background: c.id === activeId ? 'var(--mantine-color-dark-5)' : undefined,
                }}
              >
                <Text size="sm" lineClamp={2}>
                  {c.title}
                </Text>
              </UnstyledButton>
            ))}
          </Stack>
        </ScrollArea>
      </AppShell.Navbar>

      <AppShell.Main>
        <Title order={5} mb="md">
          {activeTitle}
        </Title>

        {!activeId ? (
          <Text c="dimmed">Crie uma conversa para começar.</Text>
        ) : (
          <>
            <ScrollArea
              h="calc(100vh - 220px)"
              mb="md"
              type="auto"
              viewportRef={scrollRef}
            >
              <Stack gap="md">
                {/* Stored messages */}
                {messages.map((m) => (
                  <PaperMessage key={m.id} role={m.role} content={m.content} />
                ))}

                {/* Live streaming area */}
                {streaming && (
                  <Stack gap="xs">
                    {/* Tool call cards */}
                    {pendingTools.map((tool) => (
                      <ToolCallCard key={tool.id} tool={tool} />
                    ))}

                    {/* Thinking indicator — shown while waiting for first output */}
                    {showThinking && <ThinkingIndicator />}

                    {/* Action required card (HITL) */}
                    {pendingAction && (
                      <ActionRequiredCard
                        action={pendingAction}
                        onReply={handleActionReply}
                      />
                    )}

                    {/* Streaming text */}
                    {pendingText && (
                      <PaperMessage role="assistant" content={pendingText} />
                    )}
                  </Stack>
                )}
              </Stack>
            </ScrollArea>

            <Textarea
              placeholder="Mensagem ao agente… (URLs de repo Git são detetadas automaticamente)"
              minRows={3}
              value={input}
              onChange={(e) => setInput(e.currentTarget.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey && !streaming) {
                  e.preventDefault()
                  handleSend()
                }
              }}
              disabled={streaming && !pendingAction}
            />
            <Button
              mt="sm"
              onClick={() => handleSend()}
              loading={streaming && !pendingAction}
              disabled={(!input.trim() && !pendingAction) || (streaming && !pendingAction)}
            >
              Enviar
            </Button>
          </>
        )}
      </AppShell.Main>
    </AppShell>
  )
}

function PaperMessage({ role, content }: { role: string; content: string }) {
  const isUser = role === 'user'
  return (
    <div
      className={styles.message}
      style={{
        alignSelf: isUser ? 'flex-end' : 'flex-start',
        maxWidth: '90%',
        padding: '12px 16px',
        borderRadius: 12,
        background: isUser ? 'var(--mantine-color-teal-9)' : 'var(--mantine-color-dark-6)',
        whiteSpace: 'pre-wrap',
      }}
    >
      <Text size="xs" c="dimmed" mb={4}>
        {isUser ? 'Tu' : 'Agente'}
      </Text>
      <Text size="sm">{content}</Text>
    </div>
  )
}
