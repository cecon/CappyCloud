/** Tabelas de detalhe do relatório (abaixo do resumo), na página e na versão impressa. */
import type { ReactNode } from 'react'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { cn } from '@/lib/utils'
import {
  type ReportConversation,
  type WorkspaceReport,
  formatCount,
  formatDate,
  formatMoney,
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

export function AnalystsTable({ report }: { report: WorkspaceReport }) {
  const money = (usd: number) => formatMoney(usd, report.brl)
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
              <TableHead className="text-right">Conversas</TableHead>
              <TableHead className="text-right">Custo</TableHead>
              <TableHead className="text-right">Médio por consulta</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {report.analysts.map((a) => (
              <TableRow key={a.email}>
                <TableCell>
                  <span className="font-medium">{a.label}</span>
                  <span className="ml-2 text-xs text-muted-foreground">{a.email}</span>
                </TableCell>
                <TableCell className="text-right tabular-nums">{formatCount(a.questions)}</TableCell>
                <TableCell className="text-right tabular-nums">{formatCount(a.conversations)}</TableCell>
                <TableCell className="text-right tabular-nums">{money(a.cost_usd)}</TableCell>
                <TableCell className="text-right tabular-nums">{money(a.avg_cost_per_question)}</TableCell>
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
            <TableHead className="text-right">Conversas</TableHead>
            <TableHead className="text-right">Custo</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {report.workspaces.map((w) => (
            <TableRow key={w.id}>
              <TableCell className="font-medium">{w.name}</TableCell>
              <TableCell className="text-right tabular-nums">{formatCount(w.questions)}</TableCell>
              <TableCell className="text-right tabular-nums">{formatCount(w.conversations)}</TableCell>
              <TableCell className="text-right tabular-nums">{formatMoney(w.cost_usd, report.brl)}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </ReportSection>
  )
}

export function ConversationsTable({
  report,
  rows,
}: {
  report: WorkspaceReport
  rows: ReportConversation[]
}) {
  const showWorkspace = !report.filters.workspace_id
  return (
    <ReportSection title="Conversas" hint={`${formatCount(rows.length)} com atividade no período`}>
      {rows.length === 0 ? (
        <EmptyLine />
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Data</TableHead>
              {showWorkspace && <TableHead>Workspace</TableHead>}
              <TableHead>Conversa</TableHead>
              <TableHead>Tema</TableHead>
              <TableHead>Analista</TableHead>
              <TableHead className="text-right">Consultas</TableHead>
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
                <TableCell className="text-right tabular-nums">{formatCount(c.questions)}</TableCell>
                <TableCell className="text-right tabular-nums">{formatMoney(c.cost_usd, report.brl)}</TableCell>
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
