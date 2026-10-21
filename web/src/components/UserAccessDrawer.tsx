import { useEffect, useState } from 'react'
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  type AdminUser,
  type AiModel,
  bulkGrantAiModelsByTier,
  errorToUserMessage,
  fetchAdminModels,
  fetchAdminWorkspaces,
  fetchRepositories,
  fetchSandboxes,
  fetchUserAiModelAccess,
  fetchUserRepositoryAccess,
  fetchUserSandboxAccess,
  fetchUserWorkspaceAccess,
  getToken,
  grantUserAiModelAccess,
  grantUserRepositoryAccess,
  grantUserSandboxAccess,
  grantUserWorkspaceAccess,
  type ModelTier,
  type AdminWorkspace,
  type Repository,
  revokeUserAiModelAccess,
  revokeUserRepositoryAccess,
  revokeUserSandboxAccess,
  revokeUserWorkspaceAccess,
  type Sandbox,
} from '../api'
import { AccessAlert, AccessList, BulkButton, ModelLabel, ResourceLabel } from './user-access/AccessParts'

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
  const [workspaces, setWorkspaces] = useState<Pair<AdminWorkspace>>(EMPTY())
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
    setWorkspaces(EMPTY())
    setError(null)

    // Workspaces só existem para super admin; 403 aqui não pode derrubar as outras abas.
    void Promise.all([fetchAdminWorkspaces(token), fetchUserWorkspaceAccess(token, user.id)])
      .then(([all, allowed]) =>
        setWorkspaces({ available: all, allowed: new Set(allowed), busy: new Set() }),
      )
      .catch(() => setWorkspaces({ available: [], allowed: new Set(), busy: new Set() }))

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
        style={{ width: 'min(54rem, calc(100vw - 1rem))', maxWidth: 'none' }}
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
                <TabsList className="grid w-full grid-cols-4">
                  <TabsTrigger value="workspaces">Workspaces</TabsTrigger>
                  <TabsTrigger value="sandboxes">Sandboxes</TabsTrigger>
                  <TabsTrigger value="repos">Repositórios</TabsTrigger>
                  <TabsTrigger value="models">Modelos LLM</TabsTrigger>
                </TabsList>

                <TabsContent value="workspaces" className="mt-0">
                  <AccessList
                    available={workspaces.available}
                    allowed={workspaces.allowed}
                    busy={workspaces.busy}
                    renderLabel={(w) => <ResourceLabel title={w.name} badge={w.slug} />}
                    onToggle={(id) =>
                      toggleAccess(workspaces, setWorkspaces, id, grantUserWorkspaceAccess, revokeUserWorkspaceAccess)
                    }
                  />
                </TabsContent>

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
