import { Link, useLocation } from 'react-router-dom'
import { MessageSquare, ShieldCheck } from 'lucide-react'
import { useCurrentUser } from '@/hooks/useCurrentUser'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { BrandMark } from '@/components/layout/BrandMark'
import { UserMenu } from '@/components/layout/UserMenu'
import { isAdminRoute, routeTitles } from '@/components/layout/navigation'

type AppLayoutProps = {
  children: React.ReactNode
}

export function AppLayout({ children }: AppLayoutProps) {
  const { pathname } = useLocation()
  const meta = routeTitles[pathname] ?? routeTitles['/']
  const currentUserState = useCurrentUser()
  const currentUser = currentUserState.status === 'ready' ? currentUserState.user : null
  const adminSurface = isAdminRoute(pathname)
  const chatSurface = pathname === '/chat'

  if (chatSurface) {
    return (
      <div className="h-dvh min-h-0 bg-background text-foreground">
        {children}
      </div>
    )
  }

  return (
    <div className="flex h-dvh min-h-0 flex-col bg-background text-foreground">
      <header className="flex h-14 shrink-0 items-center justify-between gap-4 border-b border-border bg-background px-4 lg:px-6">
        <div className="flex min-w-0 items-center gap-3">
          <Link to="/chat" className="flex items-center gap-3 rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" aria-label="Abrir chat">
            <BrandMark />
            <span className="hidden sm:block">
              <span className="block text-sm font-semibold leading-none">CappyCloud</span>
              <span className="mt-1 block text-[10px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
                Workspace
              </span>
            </span>
          </Link>
          <div className="hidden h-8 w-px bg-border md:block" />
          <div className="hidden min-w-0 md:block">
            <div className="flex items-center gap-2">
              <h1 className="truncate text-sm font-semibold">{meta.title}</h1>
              {adminSurface ? (
                <Badge variant="warning" className="gap-1">
                  <ShieldCheck className="size-3" />
                  Admin
                </Badge>
              ) : (
                <Badge variant="secondary" className="gap-1">
                  <MessageSquare className="size-3" />
                  Chat
                </Badge>
              )}
            </div>
            <p className="mt-1 truncate text-xs text-muted-foreground">{meta.subtitle}</p>
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {pathname !== '/chat' && (
            <Button asChild size="sm" className="hidden sm:inline-flex">
              <Link to="/chat">
                <MessageSquare className="size-4" />
                Chat
              </Link>
            </Button>
          )}
          <UserMenu user={currentUser} />
        </div>
      </header>

      <main className="min-h-0 flex-1 overflow-hidden bg-background">
        <div className="app-theme-page h-full min-h-0 overflow-auto">
          {children}
        </div>
      </main>
    </div>
  )
}
