import { ChevronDown } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { NO_TEAM, teamFilterSummary, teamLabel } from '../../reportsApi'

type Props = {
  /** Times cadastrados (nomes). "Sem time" entra sempre no fim. */
  teams: string[]
  value: string[]
  onChange: (next: string[]) => void
  className?: string
}

/** Filtro de vários times (relatório e conversas). Nada marcado = todos. */
export function TeamFilter({ teams, value, onChange, className }: Props) {
  const options = [...teams, NO_TEAM]
  const chosen = new Set(value)

  function toggle(team: string, on: boolean) {
    onChange(options.filter((t) => (t === team ? on : chosen.has(t))))
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="outline"
          className={className ?? 'h-9 min-w-[10rem] justify-between font-normal'}
          aria-label={`Filtrar por time: ${teamFilterSummary(value)}`}
        >
          <span className="truncate">{teamFilterSummary(value)}</span>
          <ChevronDown className="size-4 opacity-60" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="max-h-80 overflow-y-auto">
        {options.map((team) => (
          <DropdownMenuCheckboxItem
            key={team}
            checked={chosen.has(team)}
            onSelect={(e) => e.preventDefault()}
            onCheckedChange={(on) => toggle(team, on === true)}
          >
            {teamLabel(team)}
          </DropdownMenuCheckboxItem>
        ))}
        {value.length > 0 && (
          <>
            <DropdownMenuSeparator />
            <DropdownMenuItem onSelect={() => onChange([])}>Limpar (todos os times)</DropdownMenuItem>
          </>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
