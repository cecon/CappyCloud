import { useCallback, useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { errorToUserMessage, getToken } from '../../api'
import {
  type ReportFilters,
  type ReportOptions,
  type WorkspaceReport,
  defaultReportFilters,
  fetchReportOptions,
  fetchWorkspaceReport,
  filtersFromSearch,
  filtersToSearch,
} from '../../reportsApi'

/** Filtros na query string + relatório e opções carregados da API. */
export function useWorkspaceReport() {
  const [search, setSearch] = useSearchParams()
  const filters = useMemo(() => filtersFromSearch(search, defaultReportFilters()), [search])
  const [report, setReport] = useState<WorkspaceReport | null>(null)
  const [options, setOptions] = useState<ReportOptions | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const setFilters = useCallback(
    (next: ReportFilters) => setSearch(new URLSearchParams(filtersToSearch(next)), { replace: true }),
    [setSearch],
  )

  const load = useCallback(async () => {
    const token = getToken()
    if (!token) return
    setLoading(true)
    setError(null)
    try {
      const [nextReport, nextOptions] = await Promise.all([
        fetchWorkspaceReport(token, filters),
        fetchReportOptions(token, filters.workspaceId),
      ])
      setReport(nextReport)
      setOptions(nextOptions)
    } catch (err) {
      setError(errorToUserMessage(err))
    } finally {
      setLoading(false)
    }
  }, [filters])

  useEffect(() => {
    void load()
  }, [load])

  return { filters, setFilters, report, options, loading, error, reload: load }
}
