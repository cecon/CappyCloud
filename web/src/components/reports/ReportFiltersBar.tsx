import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'
import { type ReportFilters, type ReportOptions, isoDaysAgo } from '../../reportsApi'

const PERIOD_SHORTCUTS = [7, 15, 30, 90] as const

const selectClass = 'h-9 rounded-md border border-input bg-background px-3 text-sm'

type Props = {
  filters: ReportFilters
  options: ReportOptions | null
  onChange: (next: ReportFilters) => void
}

/** Dias do atalho ativo (quando o período termina hoje), ou `null`. */
function activeShortcut(filters: ReportFilters): number | null {
  if (filters.end !== isoDaysAgo(0)) return null
  return PERIOD_SHORTCUTS.find((days) => filters.start === isoDaysAgo(days - 1)) ?? null
}

export function ReportFiltersBar({ filters, options, onChange }: Props) {
  const active = activeShortcut(filters)
  return (
    <div className="report-controls flex flex-wrap items-end gap-3 rounded-lg border border-border bg-card p-3">
      <label className="grid gap-1 text-xs font-medium text-muted-foreground">
        Workspace
        <select
          className={selectClass}
          value={filters.workspaceId ?? ''}
          onChange={(e) => onChange({ ...filters, workspaceId: e.target.value || undefined, branch: undefined })}
        >
          <option value="">Todos os workspaces</option>
          {options?.workspaces.map((ws) => (
            <option key={ws.id} value={ws.id}>
              {ws.name}
            </option>
          ))}
        </select>
      </label>
      <label className="grid gap-1 text-xs font-medium text-muted-foreground">
        Branch
        <select
          className={selectClass}
          value={filters.branch ?? ''}
          onChange={(e) => onChange({ ...filters, branch: e.target.value || undefined })}
        >
          <option value="">Todas</option>
          {options?.branches.map((branch) => (
            <option key={branch} value={branch}>
              {branch}
            </option>
          ))}
        </select>
      </label>
      <label className="grid gap-1 text-xs font-medium text-muted-foreground">
        De
        <Input
          type="date"
          className="h-9 w-[9.5rem]"
          value={filters.start}
          max={filters.end}
          onChange={(e) => e.target.value && onChange({ ...filters, start: e.target.value })}
        />
      </label>
      <label className="grid gap-1 text-xs font-medium text-muted-foreground">
        Até
        <Input
          type="date"
          className="h-9 w-[9.5rem]"
          value={filters.end}
          min={filters.start}
          onChange={(e) => e.target.value && onChange({ ...filters, end: e.target.value })}
        />
      </label>
      <div className="flex gap-1" role="group" aria-label="Atalhos de período">
        {PERIOD_SHORTCUTS.map((days) => (
          <Button
            key={days}
            size="sm"
            variant={active === days ? 'default' : 'outline'}
            className={cn('h-9')}
            aria-pressed={active === days}
            onClick={() => onChange({ ...filters, start: isoDaysAgo(days - 1), end: isoDaysAgo(0) })}
          >
            {days} dias
          </Button>
        ))}
      </div>
    </div>
  )
}
