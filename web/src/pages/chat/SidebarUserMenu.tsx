import { Link } from 'react-router-dom'
import { redirectToLogin, type CurrentUser } from '../../api'
import { CappyIcon } from '../../components/layout/icons'
import { roleFromUser, visibleNavigationItems, type NavigationItem } from '../../components/layout/navigation'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '../../components/ui/dropdown-menu'
import styles from '../../components/chat.module.css'
import { userInitials, userRoleLabel } from './formatting'

function SidebarUserMenuLink({ item }: { item: NavigationItem }) {
  return (
    <DropdownMenuItem asChild>
      <Link to={item.to}>
        <CappyIcon name={item.icon} className="size-4" />
        <span>{item.label}</span>
      </Link>
    </DropdownMenuItem>
  )
}

export function SidebarUserMenu({ user }: { user: CurrentUser | null }) {
  const role = roleFromUser(user)
  const primary = visibleNavigationItems(role, 'primary')
  const work = visibleNavigationItems(role, 'work')
  const admin = visibleNavigationItems(role, 'admin')
  const account = visibleNavigationItems(role, 'account')

  function logout() {
    redirectToLogin()
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button type="button" className={styles.sidebarUserCard} aria-label="Abrir menu do usuário">
          <span className={styles.sidebarUserAvatar}>
            {userInitials(user?.email)}
          </span>
          <span className={styles.sidebarUserMeta}>
            <span className={styles.sidebarUserName}>
              {user?.email ?? 'CappyCloud'}
            </span>
            <span className={styles.sidebarUserRole}>
              {userRoleLabel(user)}
            </span>
          </span>
          <span className={`${styles.icon} ${styles.sidebarUserChevron}`}>expand_more</span>
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" side="right" sideOffset={10} className="w-72">
        <DropdownMenuLabel>
          <span className="block truncate text-sm text-foreground">{user?.email ?? 'Conta'}</span>
          <span className="block text-xs font-normal text-muted-foreground">{userRoleLabel(user)}</span>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        {primary.map((item) => <SidebarUserMenuLink key={item.to} item={item} />)}
        <DropdownMenuSeparator />
        <DropdownMenuLabel>Trabalho</DropdownMenuLabel>
        {work.map((item) => <SidebarUserMenuLink key={item.to} item={item} />)}
        {admin.length > 0 && (
          <>
            <DropdownMenuSeparator />
            <DropdownMenuLabel>Administração</DropdownMenuLabel>
            {admin.map((item) => <SidebarUserMenuLink key={item.to} item={item} />)}
          </>
        )}
        <DropdownMenuSeparator />
        <DropdownMenuLabel>Conta</DropdownMenuLabel>
        {account.map((item) => <SidebarUserMenuLink key={item.to} item={item} />)}
        <DropdownMenuItem onClick={logout}>
          <CappyIcon name="logout" className="size-4" />
          Sair
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
