import { useEffect, useState } from 'react'
import { Monitor, Moon, Sun } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { applyTheme, persistTheme, readTheme, type ThemeMode } from '@/lib/theme'

export function ThemeToggle() {
  const [mode, setMode] = useState<ThemeMode>(() => readTheme())

  useEffect(() => {
    applyTheme(mode)
    persistTheme(mode)
  }, [mode])

  useEffect(() => {
    const media = window.matchMedia('(prefers-color-scheme: dark)')
    const listener = () => mode === 'system' && applyTheme('system')
    media.addEventListener('change', listener)
    return () => media.removeEventListener('change', listener)
  }, [mode])

  const Icon = mode === 'light' ? Sun : mode === 'dark' ? Moon : Monitor

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon" title="Tema" aria-label="Alternar tema">
          <Icon className="size-4" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuItem onClick={() => setMode('dark')}>
          <Moon className="size-4" />
          Escuro
        </DropdownMenuItem>
        <DropdownMenuItem onClick={() => setMode('light')}>
          <Sun className="size-4" />
          Claro
        </DropdownMenuItem>
        <DropdownMenuItem onClick={() => setMode('system')}>
          <Monitor className="size-4" />
          Sistema
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
