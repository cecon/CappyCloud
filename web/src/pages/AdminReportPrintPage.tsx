import { useEffect } from 'react'
import { Printer } from 'lucide-react'
import { ExecutiveSummary } from '../components/reports/ExecutiveSummary'
import { AnalystsTable, ConversationsTable, WorkspacesTable } from '../components/reports/ReportSections'
import { useWorkspaceReport } from '../components/reports/useWorkspaceReport'
import { Button } from '../components/ui/button'
import { applyTheme } from '../lib/theme'
import { describeFilters } from '../reportsApi'

const PRINT_CSS = `
@page { size: A4 landscape; margin: 10mm; }
@media print {
  .no-print { display: none !important; }
  html, body { background: #fff !important; }
  .report-print { padding: 0 !important; max-width: none !important; }
  .report-section, .report-kpi { break-inside: avoid; box-shadow: none !important; }
  .report-slide { break-after: page; border: none !important; box-shadow: none !important; padding: 0 !important; }
  .report-bar, .report-tile, .report-slide * { print-color-adjust: exact; -webkit-print-color-adjust: exact; }
}
`

/** Versão do relatório para papel / PDF: tema claro, sem navegação nem controles. */
export function AdminReportPrintPage() {
  const { report, loading, error } = useWorkspaceReport()

  useEffect(() => {
    const root = document.documentElement
    root.classList.remove('dark')
    root.dataset.theme = 'light'
    root.style.colorScheme = 'light'
    return () => applyTheme()
  }, [])

  useEffect(() => {
    if (report) document.title = `Relatório CappyCloud · ${describeFilters(report)}`
  }, [report])

  return (
    <main className="report-print mx-auto max-w-6xl space-y-4 bg-background p-6 text-foreground">
      <style>{PRINT_CSS}</style>
      <div className="no-print flex items-center justify-between gap-3 rounded-lg border border-border bg-muted p-3 text-sm">
        <span>Use "Salvar como PDF" no destino da impressão para gerar o arquivo.</span>
        <Button size="sm" onClick={() => window.print()} disabled={!report}>
          <Printer className="size-4" />
          Imprimir / salvar PDF
        </Button>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}
      {loading && !report && <p className="text-sm text-muted-foreground">Carregando relatório…</p>}

      {report && (
        <>
          <ExecutiveSummary report={report} />
          <header className="border-b border-border pb-2">
            <h2 className="text-lg font-semibold">Detalhamento</h2>
            <p className="text-xs text-muted-foreground">
              {describeFilters(report)} · gerado em {new Date(report.generated_at).toLocaleString('pt-BR')}
            </p>
          </header>
          <AnalystsTable report={report} />
          {!report.filters.workspace_id && <WorkspacesTable report={report} />}
          <ConversationsTable report={report} rows={report.conversations} />
        </>
      )}
    </main>
  )
}
