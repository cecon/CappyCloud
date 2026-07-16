import { useEffect, useState, type ReactNode } from 'react'
import { LoaderCircle } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { cn } from '@/lib/utils'
import {
  type AdminUser,
  type AiModel,
  bulkGrantAiModelsByTier,
  errorToUserMessage,
  fetchAdminModels,
  fetchRepositories,
  fetchSandboxes,
  fetchUserAiModelAccess,
  fetchUserRepositoryAccess,
  fetchUserSandboxAccess,
  getToken,
  grantUserAiModelAccess,
  grantUserRepositoryAccess,
  grantUserSandboxAccess,
  type ModelTier,
  type Repository,
  revokeUserAiModelAccess,
  revokeUserRepositoryAccess,
  revokeUserSandboxAccess,
  type Sandbox,
} from '../api'

type Props = { user: AdminUser | null; onClose: () => void }

type Pair<T> = { available: T[] | null; allowed: Set<string>; busy: Set<string> }

const EMPTY = <T,>(): Pair<T> => ({ available: null, allowed: new Set(), busy: new Set() })

function countVisibleAllowed<T extends { id: string }>(pair: Pair<T>): number {
  if (pair.available === null) return 0
  return pair.available.reduce((total, item) => total + (pair.allowed.has(item.id) ? 1 : 0), 0)
}

export function UserAccessDrawer({ user, onClose }: Props) {
  const [sandboxes, setSandboxes] = useState<Pair<Sandbox>>(EMPTY())
  const [repos, setRepos] = useState<Pair<Repository>>(EMPTY())
  const [models, setModels] = useState<Pair<AiModel>>(EMPTY())
  const [bulkBusy, setBulkBusy] = useState<ModelTier | null>(null)
  const [error, setError] = useState<string | null>(null)
  const visibleAllowedModels = countVisibleAllowed(models)
  const visibleModels = models.available?.length ?? 0
  const hiddenAllowedModels =
    models.available === null ? 0 : Math.max(0, models.allowed.size - visibleAllowedModels)

  useEffect(() => {
    if (!user) return
    const token = getToken()
    if (!token) return
    setSandboxes(EMPTY())
    setRepos(EMPTY())
    setModels(EMPTY())
    setError(null)

    void (async () => {
      try {
        const [allSandboxes, sbAllowed, allRepos, repoAllowed, allModels, modelAllowed] =
          await Promise.all([
            fetchSandboxes(token),
            fetchUserSandboxAccess(token, user.id),
            fetchRepositories(token),
            fetchUserRepositoryAccess(token, user.id),
            fetchAdminModels(token, { only_active: true }),
            fetchUserAiModelAccess(token, user.id),
          ])
        setSandboxes({ available: allSandboxes, allowed: new Set(sbAllowed), busy: new Set() })
        setRepos({ available: allRepos, allowed: new Set(repoAllowed), busy: new Set() })
        setModels({ available: allModels, allowed: new Set(modelAllowed), busy: new Set() })
      } catch (err) {
        setError(errorToUserMessage(err))
      }
    })()
  }, [user])

  async function toggleAccess<T>(
    state: Pair<T>,
    setState: (s: Pair<T>) => void,
    resourceId: string,
    grant: (token: string, userId: string, rid: string) => Promise<void>,
    revoke: (token: string, userId: string, rid: string) => Promise<void>,
  ) {
    if (!user) return
    const token = getToken()
    if (!token) return
    const wasAllowed = state.allowed.has(resourceId)
    const nextBusy = new Set(state.busy)
    const optimisticAllowed = new Set(state.allowed)
    if (wasAllowed) optimisticAllowed.delete(resourceId)
    else optimisticAllowed.add(resourceId)
    nextBusy.add(resourceId)
    setState({ ...state, allowed: optimisticAllowed, busy: nextBusy })
    setError(null)
    try {
      if (wasAllowed) await revoke(token, user.id, resourceId)
      else await grant(token, user.id, resourceId)
      const newBusy = new Set(nextBusy)
      newBusy.delete(resourceId)
      setState({ ...state, allowed: optimisticAllowed, busy: newBusy })
    } catch (err) {
      setError(errorToUserMessage(err))
      const newBusy = new Set(nextBusy)
      newBusy.delete(resourceId)
      setState({ ...state, busy: newBusy })
    }
  }

  async function bulkByTier(tier: ModelTier) {
    if (!user) return
    const token = getToken()
    if (!token) return
    setBulkBusy(tier)
    setError(null)
    try {
      await bulkGrantAiModelsByTier(token, user.id, tier)
      const allowed = await fetchUserAiModelAccess(token, user.id)
      setModels((prev) => ({ ...prev, allowed: new Set(allowed) }))
    } catch (err) {
      setError(errorToUserMessage(err))
    } finally {
      setBulkBusy(null)
    }
  }

  return (
    <Sheet open={user !== null} onOpenChange={(open) => !open && onClose()}>
      <SheetContent
        side="right"
        className="flex h-dvh w-[min(54rem,calc(100vw-1rem))] max-w-none flex-col overflow-y-auto p-0 sm:max-w-none"
      >
        {user && (
          <>
            <SheetHeader className="border-b border-border px-6 py-5 pr-12">
              <SheetTitle>Acessos · {user.email}</SheetTitle>
              <SheetDescription>
                ADMIN vê tudo; USER vê apenas os recursos selecionados aqui.
              </SheetDescription>
            </SheetHeader>

            <div className="flex-1 space-y-4 px-6 py-5">
              {error && <AccessAlert message={error} onClose={() => setError(null)} />}
              <Tabs defaultValue="sandboxes" className="space-y-4">
                <TabsList className="grid w-full grid-cols-3">
                  <TabsTrigger value="sandboxes">Sandboxes</TabsTrigger>
                  <TabsTrigger value="repos">Repositórios</TabsTrigger>
                  <TabsTrigger value="models">Modelos LLM</TabsTrigger>
                </TabsList>

                <TabsContent value="sandboxes" className="mt-0">
                  <AccessList
                    available={sandboxes.available}
                    allowed={sandboxes.allowed}
                    busy={sandboxes.busy}
                    renderLabel={(s) => <ResourceLabel title={s.name} badge={s.host} />}
                    onToggle={(id) =>
                      toggleAccess(sandboxes, setSandboxes, id, grantUserSandboxAccess, revokeUserSandboxAccess)
                    }
                  />
                </TabsContent>

                <TabsContent value="repos" className="mt-0">
                  <AccessList
                    available={repos.available}
                    allowed={repos.allowed}
                    busy={repos.busy}
                    renderLabel={(r) => <ResourceLabel title={r.name} badge={r.slug} />}
                    onToggle={(id) =>
                      toggleAccess(repos, setRepos, id, grantUserRepositoryAccess, revokeUserRepositoryAccess)
                    }
                  />
                </TabsContent>

                <TabsContent value="models" className="mt-0">
                  <div className="space-y-3">
                    <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                      <p className="text-sm text-muted-foreground">
                        {visibleAllowedModels} de {visibleModels} modelos ativos liberados.
                        {hiddenAllowedModels > 0
                          ? ` ${hiddenAllowedModels} vínculo(s) inativo(s) oculto(s).`
                          : ''}
                      </p>
                      <div className="flex flex-wrap gap-2">
                        <BulkButton active={bulkBusy === 'free'} disabled={bulkBusy !== null} onClick={() => void bulkByTier('free')}>
                          Liberar todos free
                        </BulkButton>
                        <BulkButton active={bulkBusy === 'paid'} disabled={bulkBusy !== null} onClick={() => void bulkByTier('paid')}>
                          Liberar todos paid
                        </BulkButton>
                      </div>
                    </div>
                    <AccessList
                      available={models.available}
                      allowed={models.allowed}
                      busy={models.busy}
                      renderLabel={(m) => <ModelLabel model={m} />}
                      onToggle={(id) =>
                        toggleAccess(models, setModels, id, grantUserAiModelAccess, revokeUserAiModelAccess)
                      }
                    />
                  </div>
                </TabsContent>
              </Tabs>
            </div>
          </>
        )}
      </SheetContent>
    </Sheet>
  )
}

type AccessListProps<T extends { id: string }> = {
  available: T[] | null; allowed: Set<string>; busy: Set<string>
  renderLabel: (item: T) => ReactNode; onToggle: (id: string) => void
}

function AccessList<T extends { id: string }>({ available, allowed, busy, renderLabel, onToggle }: AccessListProps<T>) {
  if (available === null) {
    return (
      <div className="flex justify-center py-12">
        <Spinner />
      </div>
    )
  }
  if (available.length === 0) {
    return <p className="py-12 text-center text-sm text-muted-foreground">Nenhum recurso cadastrado.</p>
  }
  return (
    <div className="space-y-2">
      {available.map((item) => (
        <AccessRow
          key={item.id}
          busy={busy.has(item.id)}
          checked={allowed.has(item.id)}
          label={renderLabel(item)}
          resourceId={item.id}
          onToggle={onToggle}
        />
      ))}
    </div>
  )
}

function AccessRow({
  busy, checked, label, resourceId, onToggle,
}: {
  busy: boolean; checked: boolean; label: ReactNode; resourceId: string; onToggle: (id: string) => void
}) {
  const inputId = `access-${resourceId}`
  return (
    <div
      className={cn(
        'flex min-h-11 items-center justify-between gap-3 rounded-md border border-border bg-card px-3 py-2 text-sm transition-colors hover:bg-accent/50',
        busy && 'cursor-wait opacity-75',
      )}
    >
      <div className="flex min-w-0 items-center gap-3">
        <input id={inputId} type="checkbox" className="size-4 shrink-0 accent-primary" checked={checked} disabled={busy} onChange={() => onToggle(resourceId)} />
        <label
          htmlFor={inputId}
          className={cn('min-w-0 flex-1', busy ? 'cursor-wait' : 'cursor-pointer')}
        >
          {label}
        </label>
      </div>
      {busy && <Spinner className="size-4 shrink-0" />}
    </div>
  )
}

function ResourceLabel({ title, badge }: { title: string; badge: string }) {
  return (
    <div className="flex min-w-0 flex-wrap items-center gap-2">
      <span className="truncate font-medium">{title}</span>
      <Badge variant="outline" className="max-w-full truncate text-muted-foreground">{badge}</Badge>
    </div>
  )
}

function ModelLabel({ model }: { model: AiModel }) {
  const variant = model.tier === 'free' ? 'success' : model.tier === 'paid' ? 'secondary' : 'outline'
  return (
    <div className="flex min-w-0 flex-wrap items-center gap-2">
      <span className="truncate font-medium">{model.display_name}</span>
      <Badge variant={variant}>{model.tier}</Badge>
    </div>
  )
}

function BulkButton({ active, children, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement> & { active: boolean }) {
  return (
    <Button size="sm" variant="secondary" {...props}>
      {active && <Spinner />}
      {children}
    </Button>
  )
}

function Spinner({ className }: { className?: string }) {
  return <LoaderCircle className={cn('size-4 animate-spin', className)} aria-hidden="true" />
}

function AccessAlert({ message, onClose }: { message: string; onClose: () => void }) {
  return (
    <div className="rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm" role="alert">
      <div className="flex gap-3">
        <div className="min-w-0 flex-1"><p className="font-semibold text-foreground">Falha</p><p className="mt-1 text-muted-foreground">{message}</p></div>
        <Button type="button" variant="ghost" size="sm" onClick={onClose}>
          Fechar
        </Button>
      </div>
    </div>
  )
}
