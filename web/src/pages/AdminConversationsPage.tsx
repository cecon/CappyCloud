import { useCallback, useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { AlertTriangle, ExternalLink, RefreshCw, Search } from 'lucide-react'
import {
  type AccessibleWorkspace,
  type AdminConversationDetail,
  type AdminConversationItem,
  errorToUserMessage,
  fetchAccessibleWorkspaces,
  fetchAdminConversation,
  fetchAdminConversations,
  getToken,
} from '../api'
import { AdminConsole } from '../components/admin/AdminConsole'
import { ChatMessage } from '../components/chat/ChatMessage'
import { Badge } from '../components/ui/badge'
import { Button } from '../components/ui/button'
import { Input } from '../components/ui/input'
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '../components/ui/sheet'
import { Skeleton } from '../components/ui/skeleton'
import { cn } from '../lib/utils'

const PAGE_SIZE = 50
const ALL_WORKSPACES = ''

/**
 * Admin: todas as conversas, com busca por título, usuário ou chamado. Clicar
 * abre a conversa completa só para leitura (nada é enviado em nome do usuário).
 */
export function AdminConversationsPage() {
  const [params, setParams] = useSearchParams()
  const [query, setQuery] = useState('')
  const [appliedQuery, setAppliedQuery] = useState('')
  const [workspaceId, setWorkspaceId] = useState(ALL_WORKSPACES)
  const [workspaces, setWorkspaces] = useState<AccessibleWorkspace[]>([])
  const [items, setItems] = useState<AdminConversationItem[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const openId = params.get('open')

  const load = useCallback(async () => {
    const token = getToken()
    if (!token) return
    setLoading(true)
    setError(null)
    try {
      const result = await fetchAdminConversations(token, {
        q: appliedQuery,
        workspaceId: workspaceId || undefined,
        limit: PAGE_SIZE,
        offset: page * PAGE_SIZE,
      })
      setItems(result.items)
      setTotal(result.total)
    } catch (err) {
      setError(errorToUserMessage(err))
    } finally {
      setLoading(false)
    }
  }, [appliedQuery, workspaceId, page])

  useEffect(() => {
    void load()
  }, [load])

  useEffect(() => {
    const token = getToken()
    if (token) void fetchAccessibleWorkspaces(token).then(setWorkspaces)
  }, [])

  function open(id: string | null) {
    const next = new URLSearchParams(params)
    if (id) next.set('open', id)
    else next.delete('open')
    setParams(next, { replace: true })
  }

  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  return (
    <AdminConsole
      title="Conversas"
      description="Todas as conversas dos usuários. Busque por título, e-mail ou número do chamado e clique para ler a conversa completa."
      actions={
        <Button variant="outline" size="sm" onClick={() => void load()} disabled={loading}>
          <RefreshCw className={cn('size-4', loading && 'animate-spin')} />
          Atualizar
        </Button>
      }
    >
      <form
        className="flex flex-wrap items-center gap-2"
        onSubmit={(e) => {
          e.preventDefault()
          setPage(0)
          setAppliedQuery(query.trim())
        }}
      >
        <div className="relative min-w-[16rem] flex-1">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            className="pl-8"
            placeholder="Título, e-mail ou chamado (Enter para buscar)"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            aria-label="Buscar conversas"
          />
        </div>
        <select
          className="h-9 rounded-md border border-input bg-background px-3 text-sm"
          value={workspaceId}
          onChange={(e) => {
            setPage(0)
            setWorkspaceId(e.target.value)
          }}
          aria-label="Filtrar por workspace"
        >
          <option value={ALL_WORKSPACES}>Todos os workspaces</option>
          {workspaces.map((ws) => (
            <option key={ws.id} value={ws.id}>
              {ws.name}
            </option>
          ))}
        </select>
        <Button type="submit" size="sm">
          Buscar
        </Button>
      </form>

      {error && (
        <div className="flex items-start gap-2 rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
          <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
          <span>{error}</span>
        </div>
      )}

      <div className="overflow-hidden rounded-lg border border-border">
        <div className="divide-y divide-border">
          {loading && items.length === 0
            ? Array.from({ length: 6 }).map((_, idx) => (
                <div key={idx} className="space-y-2 p-4">
                  <Skeleton className="h-4 w-1/2" />
                  <Skeleton className="h-3 w-1/3" />
                </div>
              ))
            : items.map((item) => <ConversationRow key={item.id} item={item} onOpen={() => open(item.id)} />)}
          {!loading && items.length === 0 && (
            <p className="p-6 text-center text-sm text-muted-foreground">Nenhuma conversa encontrada.</p>
          )}
        </div>
      </div>

      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span>
          {total} conversa{total === 1 ? '' : 's'}
        </span>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" disabled={page === 0 || loading} onClick={() => setPage(page - 1)}>
            Anterior
          </Button>
          <span>
            {page + 1} / {pages}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={page + 1 >= pages || loading}
            onClick={() => setPage(page + 1)}
          >
            Próxima
          </Button>
        </div>
      </div>

      <ConversationViewer id={openId} onClose={() => open(null)} />
    </AdminConsole>
  )
}

function ConversationRow({ item, onOpen }: { item: AdminConversationItem; onOpen: () => void }) {
  return (
    <button
      type="button"
      onClick={onOpen}
      className="grid w-full gap-1 p-4 text-left hover:bg-muted/50 focus-visible:bg-muted/50 focus-visible:outline-none"
    >
      <div className="flex flex-wrap items-center gap-2">
        {item.ticket_number && (
          <Badge variant="outline" className="font-mono">
            #{item.ticket_number}
          </Badge>
        )}
        <span className="truncate text-sm font-semibold">{item.title}</span>
        {item.archived && <Badge variant="secondary">arquivada</Badge>}
      </div>
      <p className="text-xs text-muted-foreground">
        {item.user_email ?? 'sem e-mail'} · {item.workspace_name ?? 'sem workspace'} · {item.questions} pergunta
        {item.questions === 1 ? '' : 's'} · {formatCurrency(item.cost_usd)} ·{' '}
        {formatDateTime(item.last_message_at ?? item.created_at)}
      </p>
    </button>
  )
}

function ConversationViewer({ id, onClose }: { id: string | null; onClose: () => void }) {
  const [detail, setDetail] = useState<AdminConversationDetail | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!id) return
    const token = getToken()
    if (!token) return
    let cancelled = false
    fetchAdminConversation(token, id)
      .then((result) => {
        if (!cancelled) setDetail(result)
      })
      .catch((err) => {
        if (!cancelled) setError(errorToUserMessage(err))
      })
    return () => {
      cancelled = true
      setDetail(null)
      setError(null)
    }
  }, [id])

  return (
    <Sheet open={!!id} onOpenChange={(value) => !value && onClose()}>
      <SheetContent side="right" className="flex w-[min(60rem,calc(100vw-1rem))] flex-col gap-0 p-0">
        <SheetHeader className="border-b border-border p-4 text-left">
          <SheetTitle className="pr-8">{detail?.title ?? 'Carregando conversa…'}</SheetTitle>
          <SheetDescription>
            {detail ? (
              <span className="flex flex-wrap items-center gap-x-2 gap-y-1">
                {detail.ticket_number && <span className="font-mono">Chamado {detail.ticket_number}</span>}
                <span>{detail.user_email}</span>
                <span>· {detail.workspace_name ?? 'sem workspace'}</span>
                <span>· {formatDateTime(detail.created_at)}</span>
                <span>· {formatCurrency(detail.cost_usd)}</span>
                {detail.pr_url && (
                  <a className="inline-flex items-center gap-1 underline" href={detail.pr_url} target="_blank" rel="noreferrer">
                    PR <ExternalLink className="size-3" />
                  </a>
                )}
              </span>
            ) : (
              'Somente leitura'
            )}
          </SheetDescription>
        </SheetHeader>
        <div className="flex-1 space-y-4 overflow-y-auto p-4">
          {error && <p className="text-sm text-destructive">{error}</p>}
          {!detail && !error && <Skeleton className="h-24 w-full" />}
          {detail?.messages.length === 0 && <p className="text-sm text-muted-foreground">Sem mensagens.</p>}
          {detail?.messages.map((message) => (
            <ChatMessage
              key={message.id}
              role={message.role}
              content={message.content}
              authorLabel={message.role === 'user' ? (detail.user_email ?? 'Usuário') : undefined}
              meta={
                <span>
                  {formatDateTime(message.created_at)}
                  {message.role !== 'user' && message.model_used && ` · ${message.model_used}`}
                  {message.role !== 'user' &&
                    ` · ${formatTokens(message.prompt_tokens + message.completion_tokens)} tokens · ${formatCurrency(message.cost_usd)}`}
                </span>
              }
            />
          ))}
        </div>
      </SheetContent>
    </Sheet>
  )
}

function formatDateTime(value: string): string {
  return new Date(value).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' })
}

function formatCurrency(value: number): string {
  return `US$ ${value.toFixed(value < 1 ? 4 : 2)}`
}

function formatTokens(value: number): string {
  return value.toLocaleString('pt-BR')
}
