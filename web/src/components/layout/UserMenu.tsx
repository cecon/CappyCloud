import { Link, useLocation } from 'react-router-dom'
import type { CurrentUser } from '@/api'
import { setToken } from '@/api'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { CappyIcon } from './icons'
import { roleFromUser, visibleNavigationItems, type NavigationItem } from './navigation'
import { ThemeToggle } from './ThemeToggle'

type UserMenuProps = {
  user: CurrentUser | null
}

function roleLabel(user: CurrentUser | null) {
  if (!user) return 'Perfil'
  if (user.is_super_admin) return 'Super admin'
  if (user.role === 'admin') return 'Administrador'
  return 'Usuário'
}

function MenuLink({ item }: { item: NavigationItem }) {
  const location = useLocation()
  const active = location.pathname === item.to
  return (
    <DropdownMenuItem asChild>
      <Link to={item.to} aria-current={active ? 'page' : undefined}>
        <CappyIcon name={item.icon} className="size-4" />
        <span>{item.label}</span>
      </Link>
    </DropdownMenuItem>
  )
}

export function UserMenu({ user }: UserMenuProps) {
  const role = roleFromUser(user)
  const primary = visibleNavigationItems(role, 'primary')
  const work = visibleNavigationItems(role, 'work')
  const admin = visibleNavigationItems(role, 'admin')
  const account = visibleNavigationItems(role, 'account')

  function logout() {
    setToken(null)
    window.location.href = '/login'
  }

  return (
    <div className="flex items-center gap-2">
      <ThemeToggle />
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="outline" className="h-10 gap-3 px-2.5" aria-label="Abrir menu do usuario">
            <span className="grid size-7 place-items-center rounded-md bg-primary/15 text-xs font-bold text-primary">
              {user?.email.slice(0, 2).toUpperCase() ?? 'CC'}
            </span>
            <span className="hidden min-w-0 text-left sm:block">
              <span className="block max-w-44 truncate text-xs font-semibold">{user?.email ?? 'CappyCloud'}</span>
              <span className="block text-[11px] text-muted-foreground">{roleLabel(user)}</span>
            </span>
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-72">
          <DropdownMenuLabel>
            <span className="block truncate text-sm text-foreground">{user?.email ?? 'Conta'}</span>
            <span className="block text-xs font-normal text-muted-foreground">{roleLabel(user)}</span>
          </DropdownMenuLabel>
          <DropdownMenuSeparator />
          {primary.map((item) => <MenuLink key={item.to} item={item} />)}
          <DropdownMenuSeparator />
          <DropdownMenuLabel>Trabalho</DropdownMenuLabel>
          {work.map((item) => <MenuLink key={item.to} item={item} />)}
          {admin.length > 0 && (
            <>
              <DropdownMenuSeparator />
              <DropdownMenuLabel>Administração</DropdownMenuLabel>
              {admin.map((item) => <MenuLink key={item.to} item={item} />)}
            </>
          )}
          <DropdownMenuSeparator />
          <DropdownMenuLabel>Conta</DropdownMenuLabel>
          {account.map((item) => <MenuLink key={item.to} item={item} />)}
          <DropdownMenuItem onClick={logout}>
            <CappyIcon name="logout" className="size-4" />
            Sair
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  )
}
