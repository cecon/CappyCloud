/* eslint-disable react-refresh/only-export-components */
import {
  Activity,
  BarChart3,
  BookOpen,
  Bot,
  Boxes,
  Cloud,
  Code2,
  Database,
  FolderGit2,
  History,
  Home,
  KeyRound,
  LibraryBig,
  LogOut,
  MessageSquare,
  Moon,
  Network,
  PanelRightOpen,
  Plus,
  Settings,
  ShieldCheck,
  Sparkles,
  Sun,
  Users,
  type LucideIcon,
} from 'lucide-react'

export type CappyIconName =
  | 'activity'
  | 'analytics'
  | 'bot'
  | 'changePassword'
  | 'chat'
  | 'cloud'
  | 'code'
  | 'dashboard'
  | 'history'
  | 'library'
  | 'logout'
  | 'mcp'
  | 'models'
  | 'moon'
  | 'newChat'
  | 'panel'
  | 'providers'
  | 'repositories'
  | 'sandboxes'
  | 'settings'
  | 'shield'
  | 'skills'
  | 'sparkles'
  | 'sun'
  | 'users'

export const iconMap: Record<CappyIconName, LucideIcon> = {
  activity: Activity,
  analytics: BarChart3,
  bot: Bot,
  changePassword: KeyRound,
  chat: MessageSquare,
  cloud: Cloud,
  code: Code2,
  dashboard: Home,
  history: History,
  library: LibraryBig,
  logout: LogOut,
  mcp: Network,
  models: Boxes,
  moon: Moon,
  newChat: Plus,
  panel: PanelRightOpen,
  providers: Database,
  repositories: FolderGit2,
  sandboxes: Cloud,
  settings: Settings,
  shield: ShieldCheck,
  skills: BookOpen,
  sparkles: Sparkles,
  sun: Sun,
  users: Users,
}

export function CappyIcon({ name, className }: { name: CappyIconName; className?: string }) {
  const Icon = iconMap[name]
  return <Icon className={className} aria-hidden="true" />
}
