import { useState } from 'react'
import { AlertTriangle, FileSpreadsheet, FileText, Printer, RefreshCw, Tags } from 'lucide-react'
import { errorToUserMessage, getToken } from '../api'
import { AdminConsole } from '../components/admin/AdminConsole'
import { ReportFiltersBar } from '../components/reports/ReportFiltersBar'
import { ExecutiveSummary } from '../components/reports/ExecutiveSummary'
import { AnalystsTable, ConversationsTable, WorkspacesTable } from '../components/reports/ReportSections'
import { ThemeRulesDialog } from '../components/reports/ThemeRulesDialog'
import { useWorkspaceReport } from '../components/reports/useWorkspaceReport'
import { Button } from '../components/ui/button'
import { Skeleton } from '../components/ui/skeleton'
import { cn } from '../lib/utils'
import { downloadWorkspaceReport, filtersToSearch } from '../reportsApi'

export function AdminReportsPage() {
  const { filters, setFilters, report, options, loading, error, reload } = useWorkspaceReport()
  const [exporting, setExporting] = useState<'xlsx' | 'csv' | null>(null)
  const [exportError, setExportError] = useState<string | null>(null)
  const [themesOpen, setThemesOpen] = useState(false)
  const workspace = options?.workspaces.find((ws) => ws.id === filters.workspaceId)

  async function exportAs(format: 'xlsx' | 'csv') {
    const token = getToken()
    if (!token) return
    setExporting(format)
    setExportError(null)
    try {
      await downloadWorkspaceReport(token, filters, format)
    } catch (err) {
      setExportError(errorToUserMessage(err))
    } finally {
      setExporting(null)
    }
  }

  const problem = error ?? exportError
  return (
    <AdminConsole
      title="Relatórios"
      description="Uso da Cappy por workspace, branch e período, no formato do resumo levado à Diretoria."
      actions={
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => void reload()} disabled={loading}>
            <RefreshCw className={cn('size-4', loading && 'animate-spin')} />
            Atualizar
          </Button>
          <Button variant="outline" size="sm" onClick={() => void exportAs('xlsx')} disabled={!report || exporting !== null}>
            <FileSpreadsheet className="size-4" />
            {exporting === 'xlsx' ? 'Gerando…' : 'Exportar XLSX'}
          </Button>
          <Button variant="outline" size="sm" onClick={() => void exportAs('csv')} disabled={!report || exporting !== null}>
            <FileText className="size-4" />
            {exporting === 'csv' ? 'Gerando…' : 'CSV'}
          </Button>
          <Button asChild variant="outline" size="sm">
            <a href={`/admin/reports/print?${filtersToSearch(filters)}`} target="_blank" rel="noreferrer">
              <Printer className="size-4" />
              Versão para impressão
            </a>
          </Button>
          {options?.can_edit_themes && workspace && (
            <Button variant="outline" size="sm" onClick={() => setThemesOpen(true)}>
              <Tags className="size-4" />
              Temas
            </Button>
          )}
        </div>
      }
    >
      <ReportFiltersBar filters={filters} options={options} onChange={setFilters} />

      {problem && (
        <div className="flex items-start gap-2 rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
          <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
          <span>{problem}</span>
        </div>
      )}

      {loading && !report ? (
        <div className="space-y-3">
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {Array.from({ length: 4 }).map((_, idx) => (
              <Skeleton key={idx} className="h-28 w-full" />
            ))}
          </div>
          <Skeleton className="h-64 w-full" />
        </div>
      ) : report ? (
        <div className={cn('space-y-4', loading && 'opacity-60')}>
          <ExecutiveSummary report={report} />
          <div className="grid gap-4 xl:grid-cols-2">
            <AnalystsTable report={report} />
            {!report.filters.workspace_id && <WorkspacesTable report={report} />}
          </div>
          <ConversationsTable report={report} rows={report.conversations} />
        </div>
      ) : null}

      {workspace && (
        <ThemeRulesDialog
          workspaceId={workspace.id}
          workspaceName={workspace.name}
          open={themesOpen}
          onOpenChange={setThemesOpen}
          onSaved={() => void reload()}
        />
      )}
    </AdminConsole>
  )
}
