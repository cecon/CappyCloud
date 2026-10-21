import { describe, expect, it } from 'vitest'
import {
  type WorkspaceReport,
  describeFilters,
  filtersFromSearch,
  filtersToSearch,
  formatBrl,
  formatDate,
  formatMoney,
  formatUsd,
  isoDaysAgo,
} from './reportsApi'

describe('reportsApi helpers', () => {
  it('computes local dates for period shortcuts', () => {
    const today = new Date(2026, 9, 9, 23, 30)
    expect(isoDaysAgo(0, today)).toBe('2026-10-09')
    expect(isoDaysAgo(29, today)).toBe('2026-09-10')
    expect(isoDaysAgo(9, new Date(2026, 0, 3))).toBe('2025-12-25')
  })

  it('round-trips filters through the query string', () => {
    const filters = { workspaceId: 'ws-1', branch: 'main', start: '2026-09-01', end: '2026-09-30' }
    const search = new URLSearchParams(filtersToSearch(filters))
    expect(filtersFromSearch(search, { start: 'x', end: 'y' })).toEqual(filters)
    expect(filtersFromSearch(new URLSearchParams(), { start: 'a', end: 'b' })).toEqual({
      workspaceId: undefined,
      branch: undefined,
      start: 'a',
      end: 'b',
    })
    expect(filtersToSearch({ start: 'a', end: 'b' })).toBe('start=a&end=b')
  })

  it('formats money and dates for the report', () => {
    expect(formatUsd(0)).toBe('$0.00')
    expect(formatUsd(0.0123)).toBe('$0.0123')
    expect(formatUsd(12.5)).toBe('$12.50')
    expect(formatDate('2026-09-07T10:00:00-03:00')).toBe('07/09/2026')
  })

  it('shows R$ when there is a PTAX quote and US$ otherwise', () => {
    const brl = { rate: 5.0119, quoted_on: '2026-10-08', source: 'PTAX' }
    expect(formatBrl(8.56).replace(/\s/g, ' ')).toBe('R$ 8,56')
    expect(formatMoney(2, brl).replace(/\s/g, ' ')).toBe('R$ 10,02')
    expect(formatMoney(2, null)).toBe('$2.00')
  })

  it('describes the applied filters', () => {
    const report = {
      filters: { workspace_name: null, branch: 'main', start: '2026-09-01', end: '2026-09-30' },
    } as WorkspaceReport
    expect(describeFilters(report)).toBe('Todos os workspaces · 01/09/2026 a 30/09/2026 · branch main')
  })
})
