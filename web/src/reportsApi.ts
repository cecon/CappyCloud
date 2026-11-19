/** Cliente de /api/admin/reports — relatório de uso por workspace. */
import { apiFetch, formatApiErrorPayload } from './api'

export type ReportFilters = {
  workspaceId?: string
  branch?: string
  /** Nomes dos times (vazio = todos); `NO_TEAM` = quem não tem time. */
  teams?: string[]
  start: string
  end: string
}

/** Valor do filtro de time para "Sem time" (igual ao da API). */
export const NO_TEAM = '__none__'

export type ReportWorkspaceOption = { id: string; slug: string; name: string }

export type ReportOptions = {
  workspaces: ReportWorkspaceOption[]
  branches: string[]
  can_edit_themes: boolean
  teams: string[]
}

export type ReportTotals = {
  questions: number
  conversations: number
  tickets: number
  conversations_without_ticket: number
  analysts: number
  messages: number
  cost_usd: number
  avg_cost_per_question: number
  avg_cost_per_conversation: number
  avg_cost_per_analyst: number
}

export type ReportAnalyst = {
  email: string
  label: string
  team: string
  questions: number
  conversations: number
  cost_usd: number
  avg_cost_per_question: number
}

type Usage = { questions: number; conversations: number; cost_usd: number }

export type ReportWeek = Usage & { start: string; end: string; label: string }
export type ReportTheme = Usage & { key: string; label: string; share: number }
export type ReportWorkspaceTotals = ReportWorkspaceOption & Usage
export type ReportTeam = Usage & { name: string; analysts: number; share: number }

export type ReportConversation = {
  conversation_id: string
  workspace_slug: string
  analyst_email: string
  team: string
  ticket_number: string | null
  title: string
  theme_key: string
  theme_label: string
  branches: string[]
  questions: number
  messages: number
  cost_usd: number
  first_message_at: string
  last_message_at: string
}

/** Cotação PTAX usada para os valores em R$ (`null` se o Banco Central não respondeu). */
export type BrlRate = { rate: number; quoted_on: string; source: string }

export type WorkspaceReport = {
  generated_at: string
  filters: {
    workspace_id: string | null
    workspace_name: string | null
    branch: string | null
    teams: string[]
    start: string
    end: string
    timezone: string
    currency: 'USD'
  }
  brl: BrlRate | null
  totals: ReportTotals
  analysts: ReportAnalyst[]
  weeks: ReportWeek[]
  themes: ReportTheme[]
  workspaces: ReportWorkspaceTotals[]
  conversations: ReportConversation[]
  teams: ReportTeam[]
}

export type ThemeRule = { key: string; label: string; patterns: string[] }

export type ThemeConfig = {
  workspace_id: string
  preset: string | null
  custom: boolean
  rules: ThemeRule[]
  presets: { key: string; label: string }[]
}

function reportParams(filters: ReportFilters): URLSearchParams {
  const params = new URLSearchParams({ start: filters.start, end: filters.end })
  if (filters.workspaceId) params.set('workspace_id', filters.workspaceId)
  if (filters.branch) params.set('branch', filters.branch)
  for (const team of filters.teams ?? []) params.append('team', team)
  return params
}

async function request<T>(token: string, path: string, fallback: string, init: RequestInit = {}): Promise<T> {
  const res = await apiFetch(`/api/admin/reports${path}`, {
    ...init,
    headers: { Authorization: `Bearer ${token}`, ...(init.headers ?? {}) },
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || fallback)
  }
  return (await res.json()) as T
}

export function fetchReportOptions(token: string, workspaceId?: string): Promise<ReportOptions> {
  const query = workspaceId ? `?workspace_id=${encodeURIComponent(workspaceId)}` : ''
  return request(token, `/options${query}`, 'Falha ao carregar os filtros do relatório')
}

export function fetchWorkspaceReport(token: string, filters: ReportFilters): Promise<WorkspaceReport> {
  return request(token, `/workspace?${reportParams(filters)}`, 'Falha ao carregar o relatório')
}

export async function downloadWorkspaceReport(
  token: string,
  filters: ReportFilters,
  format: 'xlsx' | 'csv',
): Promise<void> {
  const params = reportParams(filters)
  params.set('format', format)
  const res = await apiFetch(`/api/admin/reports/workspace/export?${params}`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(formatApiErrorPayload(err) || 'Falha ao exportar o relatório')
  }
  const disposition = res.headers.get('content-disposition') ?? ''
  const name = /filename="([^"]+)"/.exec(disposition)?.[1] ?? `relatorio.${format}`
  const url = URL.createObjectURL(await res.blob())
  const link = document.createElement('a')
  link.href = url
  link.download = name
  link.click()
  URL.revokeObjectURL(url)
}

export function fetchReportThemes(token: string, workspaceId: string): Promise<ThemeConfig> {
  return request(token, `/themes/${workspaceId}`, 'Falha ao carregar os temas')
}

export function updateReportThemes(
  token: string,
  workspaceId: string,
  body: { preset: string | null; rules: ThemeRule[] | null },
): Promise<ThemeConfig> {
  return request(token, `/themes/${workspaceId}`, 'Falha ao salvar os temas', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

/** Filtros ↔ query string da página (a versão para impressão reaproveita). */
export function filtersToSearch(filters: ReportFilters): string {
  return reportParams(filters).toString()
}

export function filtersFromSearch(search: URLSearchParams, fallback: ReportFilters): ReportFilters {
  return {
    workspaceId: search.get('workspace_id') ?? fallback.workspaceId,
    branch: search.get('branch') ?? fallback.branch,
    teams: search.has('team') ? search.getAll('team') : fallback.teams,
    start: search.get('start') ?? fallback.start,
    end: search.get('end') ?? fallback.end,
  }
}

/** Data local `YYYY-MM-DD`, `days` dias antes de hoje (0 = hoje). */
export function isoDaysAgo(days: number, today: Date = new Date()): string {
  const d = new Date(today.getFullYear(), today.getMonth(), today.getDate() - days)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

export function defaultReportFilters(): ReportFilters {
  return { start: isoDaysAgo(29), end: isoDaysAgo(0) }
}

export function formatUsd(value: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
    maximumFractionDigits: value !== 0 && Math.abs(value) < 1 ? 4 : 2,
  }).format(value)
}

export function formatBrl(value: number): string {
  return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(value)
}

/** Valor em R$ quando há cotação; senão em US$. */
export function formatMoney(usd: number, brl: BrlRate | null): string {
  return brl ? formatBrl(usd * brl.rate) : formatUsd(usd)
}

export function formatCount(value: number): string {
  return new Intl.NumberFormat('pt-BR').format(value)
}

export function formatPercent(share: number): string {
  return `${Math.round(share * 100)}%`
}

export function formatDate(iso: string): string {
  const [y, m, d] = iso.slice(0, 10).split('-')
  return `${d}/${m}/${y}`
}

/** Times só aparecem quando algum foi cadastrado (todo mundo "Sem time" não diz nada). */
export function hasTeams(report: WorkspaceReport): boolean {
  return report.teams.some((t) => t.name !== 'Sem time')
}

export function teamLabel(team: string): string {
  return team === NO_TEAM ? 'Sem time' : team
}

/** Resumo do filtro de times: "Todos", o nome do time ou "N times". */
export function teamFilterSummary(value: string[]): string {
  if (value.length === 0) return 'Todos'
  if (value.length === 1) return teamLabel(value[0])
  return `${value.length} times`
}

/** Workspace, período, branch e time — cabeçalho do relatório. */
export function describeFilters(report: WorkspaceReport): string {
  const f = report.filters
  return [
    f.workspace_name ?? 'Todos os workspaces',
    `${formatDate(f.start)} a ${formatDate(f.end)}`,
    f.branch ? `branch ${f.branch}` : 'todas as branches',
    ...(f.teams?.length ? [`${f.teams.length > 1 ? 'times' : 'time'} ${f.teams.map(teamLabel).join(', ')}`] : []),
  ].join(' · ')
}
