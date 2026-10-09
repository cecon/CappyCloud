import { useEffect } from 'react'
import { Printer } from 'lucide-react'
import {
  AnalystsTable,
  ConsultationsTable,
  ReportKpis,
  ThemeDistribution,
  WeeklyEvolution,
  WorkspacesTable,
} from '../components/reports/ReportSections'
import { useWorkspaceReport } from '../components/reports/useWorkspaceReport'
import { Button } from '../components/ui/button'
import { applyTheme } from '../lib/theme'
import { describeFilters } from '../reportsApi'

const PRINT_CSS = `
@page { size: A4; margin: 14mm; }
@media print {
  .no-print { display: none !important; }
  html, body { background: #fff !important; }
  .report-print { padding: 0 !important; max-width: none !important; }
  .report-section, .report-kpi { break-inside: avoid; box-shadow: none !important; }
  .report-bar { print-color-adjust: exact; -webkit-print-color-adjust: exact; }
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
    <main className="report-print mx-auto max-w-5xl space-y-4 bg-background p-6 text-foreground">
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
          <header className="border-b border-border pb-3">
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">CappyCloud</p>
            <h1 className="mt-1 text-2xl font-semibold">Relatório de uso</h1>
            <p className="mt-1 text-sm">{describeFilters(report)}</p>
            <p className="mt-1 text-xs text-muted-foreground">
              Gerado em {new Date(report.generated_at).toLocaleString('pt-BR')} · datas em {report.filters.timezone} ·
              valores em US$, somados do custo real informado pelo provedor (sem conversão de moeda)
            </p>
          </header>
          <ReportKpis report={report} />
          <WeeklyEvolution report={report} />
          <ThemeDistribution report={report} />
          <AnalystsTable report={report} />
          {!report.filters.workspace_id && <WorkspacesTable report={report} />}
          <ConsultationsTable rows={report.consultations} showWorkspace={!report.filters.workspace_id} />
        </>
      )}
    </main>
  )
}
