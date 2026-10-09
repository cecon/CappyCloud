/** Blocos do relatório de uso, usados pela página do admin e pela versão impressa. */
import type { ReactNode } from 'react'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { cn } from '@/lib/utils'
import {
  type ReportConsultation,
  type WorkspaceReport,
  formatCount,
  formatDate,
  formatUsd,
} from '../../reportsApi'

export function ReportSection({
  title,
  hint,
  children,
  className,
}: {
  title: string
  hint?: string
  children: ReactNode
  className?: string
}) {
  return (
    <section className={cn('report-section rounded-lg border border-border bg-card p-4', className)}>
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="text-sm font-semibold">{title}</h3>
        {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
      </div>
      {children}
    </section>
  )
}

function Kpi({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="report-kpi rounded-lg border border-border bg-card p-4">
      <p className="text-xs font-medium text-muted-foreground">{label}</p>
      <p className="mt-1 text-2xl font-semibold tabular-nums">{value}</p>
      {hint && <p className="mt-1 text-xs text-muted-foreground">{hint}</p>}
    </div>
  )
}

export function ReportKpis({ report }: { report: WorkspaceReport }) {
  const t = report.totals
  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
      <Kpi label="Consultas" value={formatCount(t.consultations)} hint={`${formatCount(t.messages)} mensagens no período`} />
      <Kpi label="Analistas distintos" value={formatCount(t.analysts)} />
      <Kpi label="Custo total" value={formatUsd(t.cost_usd)} hint="Soma do custo real do provedor" />
      <Kpi label="Custo médio por consulta" value={formatUsd(t.avg_cost_per_consultation)} />
      <Kpi label="Custo médio por analista" value={formatUsd(t.avg_cost_per_analyst)} />
    </div>
  )
}

function Bar({ value, max }: { value: number; max: number }) {
  const width = max > 0 ? Math.max(value > 0 ? 2 : 0, (value / max) * 100) : 0
  return (
    <div className="h-2 w-full rounded-full bg-muted" aria-hidden="true">
      <div className="report-bar h-2 rounded-full bg-primary" style={{ width: `${width}%` }} />
    </div>
  )
}

export function WeeklyEvolution({ report }: { report: WorkspaceReport }) {
  const max = Math.max(0, ...report.weeks.map((w) => w.cost_usd))
  return (
    <ReportSection title="Evolução semanal" hint="Semana ISO (segunda a domingo)">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Semana</TableHead>
            <TableHead className="text-right">Consultas</TableHead>
            <TableHead className="text-right">Custo</TableHead>
            <TableHead className="w-[40%]">
              <span className="sr-only">Custo relativo</span>
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {report.weeks.map((w) => (
            <TableRow key={w.week}>
              <TableCell>
                <span className="font-medium">{w.week}</span>
                <span className="ml-2 text-xs text-muted-foreground">desde {formatDate(w.start)}</span>
              </TableCell>
              <TableCell className="text-right tabular-nums">{formatCount(w.consultations)}</TableCell>
              <TableCell className="text-right tabular-nums">{formatUsd(w.cost_usd)}</TableCell>
              <TableCell>
                <Bar value={w.cost_usd} max={max} />
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      <p className="mt-2 text-xs text-muted-foreground">
        Uma consulta ativa em duas semanas conta nas duas; o total do período não é a soma das semanas.
      </p>
    </ReportSection>
  )
}

export function ThemeDistribution({ report }: { report: WorkspaceReport }) {
  const total = report.totals.consultations
  return (
    <ReportSection title="Distribuição por tema" hint="Regras sobre o título e a primeira pergunta">
      {report.themes.length === 0 ? (
        <EmptyLine />
      ) : (
        <ul className="space-y-3">
          {report.themes.map((t) => (
            <li key={t.key} className="space-y-1">
              <div className="flex items-baseline justify-between gap-3 text-sm">
                <span className="min-w-0 truncate font-medium">{t.label}</span>
                <span className="shrink-0 tabular-nums text-muted-foreground">
                  {formatCount(t.consultations)} · {total ? Math.round((t.consultations / total) * 100) : 0}% ·{' '}
                  {formatUsd(t.cost_usd)}
                </span>
              </div>
              <Bar value={t.consultations} max={total} />
            </li>
          ))}
        </ul>
      )}
    </ReportSection>
  )
}

export function AnalystsTable({ report }: { report: WorkspaceReport }) {
  return (
    <ReportSection title="Por analista" hint="Identificado pelo e-mail do usuário">
      {report.analysts.length === 0 ? (
        <EmptyLine />
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Analista</TableHead>
              <TableHead className="text-right">Consultas</TableHead>
              <TableHead className="text-right">Custo</TableHead>
              <TableHead className="text-right">Médio</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {report.analysts.map((a) => (
              <TableRow key={a.email}>
                <TableCell>
                  <span className="font-medium">{a.label}</span>
                  <span className="ml-2 text-xs text-muted-foreground">{a.email}</span>
                </TableCell>
                <TableCell className="text-right tabular-nums">{formatCount(a.consultations)}</TableCell>
                <TableCell className="text-right tabular-nums">{formatUsd(a.cost_usd)}</TableCell>
                <TableCell className="text-right tabular-nums">{formatUsd(a.avg_cost_usd)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </ReportSection>
  )
}

export function WorkspacesTable({ report }: { report: WorkspaceReport }) {
  return (
    <ReportSection title="Por workspace">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Workspace</TableHead>
            <TableHead className="text-right">Consultas</TableHead>
            <TableHead className="text-right">Custo</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {report.workspaces.map((w) => (
            <TableRow key={w.id}>
              <TableCell className="font-medium">{w.name}</TableCell>
              <TableCell className="text-right tabular-nums">{formatCount(w.consultations)}</TableCell>
              <TableCell className="text-right tabular-nums">{formatUsd(w.cost_usd)}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </ReportSection>
  )
}

export function ConsultationsTable({
  rows,
  showWorkspace,
}: {
  rows: ReportConsultation[]
  showWorkspace: boolean
}) {
  return (
    <ReportSection title="Consultas" hint={`${formatCount(rows.length)} no período`}>
      {rows.length === 0 ? (
        <EmptyLine />
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Data</TableHead>
              {showWorkspace && <TableHead>Workspace</TableHead>}
              <TableHead>Consulta</TableHead>
              <TableHead>Tema</TableHead>
              <TableHead>Analista</TableHead>
              <TableHead className="text-right">Custo</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((c) => (
              <TableRow key={c.conversation_id}>
                <TableCell className="whitespace-nowrap tabular-nums">{formatDate(c.last_message_at)}</TableCell>
                {showWorkspace && <TableCell>{c.workspace_slug}</TableCell>}
                <TableCell className="max-w-[28rem]">
                  <span className="line-clamp-2">{c.title}</span>
                  {c.ticket_number && <span className="text-xs text-muted-foreground">Chamado {c.ticket_number}</span>}
                </TableCell>
                <TableCell className="text-xs">{c.theme_label}</TableCell>
                <TableCell className="text-xs">{c.analyst_email.split('@')[0]}</TableCell>
                <TableCell className="text-right tabular-nums">{formatUsd(c.cost_usd)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </ReportSection>
  )
}

function EmptyLine() {
  return <p className="py-6 text-center text-sm text-muted-foreground">Nenhuma consulta no período.</p>
}
