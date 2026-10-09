/**
 * "Resumo de uso e investimento" — o slide que o time leva à Diretoria, gerado
 * a partir do relatório. Fica sempre em fundo claro (vira página de apresentação
 * e PDF), inclusive com o app em tema escuro.
 */
import type { ComponentType, ReactNode } from 'react'
import { CircleDollarSign, Database, MessageSquare, Users } from 'lucide-react'
import {
  type ReportWeek,
  type WorkspaceReport,
  formatCount,
  formatDate,
  formatMoney,
  formatUsd,
} from '../../reportsApi'

const NAVY = '#0f2a44'

const TILES = {
  navy: { bg: NAVY, fg: '#ffffff', muted: 'rgba(255,255,255,0.75)' },
  cyan: { bg: '#18c5e6', fg: NAVY, muted: 'rgba(15,42,68,0.8)' },
  purple: { bg: '#9b5cf6', fg: '#ffffff', muted: 'rgba(255,255,255,0.8)' },
  orange: { bg: '#f97316', fg: '#ffffff', muted: 'rgba(255,255,255,0.85)' },
} as const

function Tile({
  tone,
  icon: Icon,
  label,
  value,
  hint,
}: {
  tone: keyof typeof TILES
  icon: ComponentType<{ className?: string }>
  label: string
  value: string
  hint: string
}) {
  const c = TILES[tone]
  return (
    <div className="report-tile flex gap-3 rounded-lg p-4" style={{ background: c.bg, color: c.fg }}>
      <Icon className="mt-0.5 size-7 shrink-0" aria-hidden="true" />
      <div className="min-w-0">
        <p className="text-sm font-semibold leading-tight">{label}</p>
        <p className="mt-1 text-3xl font-bold leading-none tabular-nums">{value}</p>
        <p className="mt-2 text-xs leading-snug" style={{ color: c.muted }}>
          {hint}
        </p>
      </div>
    </div>
  )
}

function Panel({ title, hint, children }: { title: string; hint: string; children: ReactNode }) {
  return (
    <div className="report-section rounded-lg border border-slate-200 bg-white p-4">
      <p className="text-sm font-bold" style={{ color: NAVY }}>
        {title}
      </p>
      <p className="text-xs text-slate-500">{hint}</p>
      <div className="mt-3">{children}</div>
    </div>
  )
}

/** Colunas por semana, com o valor em cima e o intervalo de datas embaixo. */
function WeeklyBars({ weeks }: { weeks: ReportWeek[] }) {
  if (weeks.length === 0) return null
  const W = 520
  const H = 200
  const top = 18
  const bottom = 24
  const left = 30
  const plotH = H - top - bottom
  const max = Math.max(1, ...weeks.map((w) => w.questions))
  const step = Math.pow(10, Math.floor(Math.log10(max)))
  const ceil = Math.ceil(max / step) * step
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((f) => Math.round(ceil * f))
  const slot = (W - left) / weeks.length
  const barW = Math.min(56, slot * 0.6)
  const y = (v: number) => top + plotH - (v / ceil) * plotH
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="h-auto w-full" role="img" aria-label="Consultas por semana">
      {[...new Set(ticks)].map((t) => (
        <g key={t}>
          <line x1={left} x2={W} y1={y(t)} y2={y(t)} stroke="#e2e8f0" strokeWidth={1} />
          <text x={left - 6} y={y(t) + 3} textAnchor="end" fontSize={10} fill="#64748b">
            {t}
          </text>
        </g>
      ))}
      {weeks.map((w, i) => {
        const cx = left + slot * i + slot / 2
        return (
          <g key={w.start}>
            <rect
              className="report-bar"
              x={cx - barW / 2}
              y={y(w.questions)}
              width={barW}
              height={Math.max(0, top + plotH - y(w.questions))}
              fill={NAVY}
            />
            <text x={cx} y={y(w.questions) - 5} textAnchor="middle" fontSize={12} fontWeight={700} fill={NAVY}>
              {w.questions}
            </text>
            <text x={cx} y={H - 6} textAnchor="middle" fontSize={10} fill="#475569">
              {w.label}
            </text>
          </g>
        )
      })}
    </svg>
  )
}

function ThemeBars({ report }: { report: WorkspaceReport }) {
  const max = Math.max(0, ...report.themes.map((t) => t.share))
  if (report.themes.length === 0) {
    return <p className="py-8 text-center text-sm text-slate-500">Nenhuma consulta no período.</p>
  }
  return (
    <ul className="space-y-2.5">
      {report.themes.map((t) => (
        <li key={t.key} className="grid grid-cols-[minmax(0,11rem)_1fr_2.5rem] items-center gap-3 text-xs">
          <span className="truncate text-right text-slate-700" title={t.label}>
            {t.label}
          </span>
          <span className="h-3.5 rounded-sm bg-slate-100">
            <span
              className="report-bar block h-3.5 rounded-sm"
              style={{ width: `${max ? (t.share / max) * 100 : 0}%`, background: NAVY }}
            />
          </span>
          <span className="text-right font-bold tabular-nums" style={{ color: NAVY }}>
            {Math.round(t.share * 100)}%
          </span>
        </li>
      ))}
    </ul>
  )
}

function analystsHint(report: WorkspaceReport): string {
  const names = report.analysts.map((a) => a.label)
  if (names.length === 0) return 'Nenhum analista no período.'
  if (names.length <= 3) return names.join(', ')
  return `${names.slice(0, 3).join(', ')} e mais ${names.length - 3}`
}

export function ExecutiveSummary({ report }: { report: WorkspaceReport }) {
  const { totals, filters, brl } = report
  const scope = [filters.workspace_name ?? 'Todos os workspaces', filters.branch && `branch ${filters.branch}`]
    .filter(Boolean)
    .join(' · ')
  return (
    <section className="report-slide space-y-4 rounded-xl border border-slate-200 bg-white p-5 text-slate-900 shadow-sm">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-600">Cappy · {scope}</p>
          <h2 className="mt-1 text-3xl font-bold" style={{ color: NAVY }}>
            Resumo de uso e investimento
          </h2>
          <p className="mt-1 text-sm text-slate-600">Visão consolidada do uso da Cappy no período analisado.</p>
        </div>
        <div className="rounded-md bg-indigo-50 px-4 py-2 text-xs text-slate-600">
          Período analisado
          <p className="text-sm font-bold" style={{ color: NAVY }}>
            {formatDate(filters.start)} a {formatDate(filters.end)}
          </p>
        </div>
      </header>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Tile tone="navy" icon={MessageSquare} label="Total de consultas" value={formatCount(totals.questions)}
          hint={`Perguntas realizadas à Cappy no período, em ${formatCount(totals.conversations)} conversas.`} />
        <Tile tone="cyan" icon={Users} label="Analistas" value={formatCount(totals.analysts)} hint={analystsHint(report)} />
        <Tile tone="purple" icon={Database} label="Custo total" value={formatMoney(totals.cost_usd, brl)}
          hint={`Custo com processamento das consultas no período${brl ? ` (${formatUsd(totals.cost_usd)})` : ''}.`} />
        <Tile tone="orange" icon={CircleDollarSign} label="Custo médio por consulta"
          value={formatMoney(totals.avg_cost_per_question, brl)} hint="Valor médio por pergunta feita à Cappy." />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Panel title="Evolução de consultas" hint="Quantidade de consultas por semana.">
          <WeeklyBars weeks={report.weeks} />
        </Panel>
        <Panel title="Distribuição das consultas" hint="Principais temas abordados.">
          <ThemeBars report={report} />
        </Panel>
      </div>

      <p className="text-[11px] leading-snug text-slate-500">
        Custo real informado pelo provedor do modelo (US$).{' '}
        {brl
          ? `Convertido em R$ pela ${brl.source} de ${formatDate(brl.quoted_on)}: R$ ${brl.rate.toLocaleString('pt-BR', { minimumFractionDigits: 4 })} por US$ 1.`
          : 'Sem cotação do Banco Central no momento: valores em US$.'}{' '}
        Datas no fuso {filters.timezone}; semanas de 7 dias a partir do início do período.
      </p>
    </section>
  )
}
