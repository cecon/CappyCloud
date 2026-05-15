import { useEffect, useState } from 'react'
import {
  AuthError,
  createMcpServer,
  deleteMcpServer,
  exportMcpConfig,
  fetchMcpServers,
  getToken,
  setToken,
  updateMcpServer,
  type McpServer,
  type McpServerCreate,
} from '../api'
import styles from './settings.module.css'
import mcpStyles from './McpPage.module.css'

const EMPTY_FORM: McpServerCreate = {
  name: '',
  command: '',
  args: [],
  env: {},
  enabled: true,
}

/**
 * Página de gestão de servidores MCP (Model Context Protocol).
 * Permite criar, editar, ativar/desativar e eliminar servidores MCP.
 * Mostra também o JSON de exportação no formato esperado pelo openclaude.
 */
export function McpPage() {
  const token = getToken()!

  const [servers, setServers] = useState<McpServer[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [editingId, setEditingId] = useState<string | null>(null)
  const [form, setForm] = useState<McpServerCreate>(EMPTY_FORM)
  const [argsText, setArgsText] = useState('')
  const [envRows, setEnvRows] = useState<{ key: string; value: string }[]>([])
  const [saving, setSaving] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)

  const [showExport, setShowExport] = useState(false)
  const [exportJson, setExportJson] = useState('')
  const [exporting, setExporting] = useState(false)

  const [deletingId, setDeletingId] = useState<string | null>(null)

  useEffect(() => {
    void loadServers()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function loadServers() {
    setLoading(true)
    setError(null)
    try {
      const list = await fetchMcpServers(token)
      setServers(list)
    } catch (err) {
      if (err instanceof AuthError) {
        setToken(null)
        window.location.href = '/login'
        return
      }
      setError(err instanceof Error ? err.message : 'Erro ao carregar servidores MCP')
    } finally {
      setLoading(false)
    }
  }

  function startCreate() {
    setEditingId(null)
    setForm(EMPTY_FORM)
    setArgsText('')
    setEnvRows([])
    setFormError(null)
  }

  function startEdit(s: McpServer) {
    setEditingId(s.id)
    setForm({ name: s.name, command: s.command, args: s.args, env: s.env, enabled: s.enabled })
    setArgsText(s.args.join(', '))
    setEnvRows(Object.entries(s.env).map(([key, value]) => ({ key, value })))
    setFormError(null)
  }

  function cancelForm() {
    setEditingId(null)
    setForm(EMPTY_FORM)
    setArgsText('')
    setEnvRows([])
    setFormError(null)
  }

  function buildPayload(): McpServerCreate {
    const args = argsText
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean)
    const env: Record<string, string> = {}
    for (const row of envRows) {
      if (row.key.trim()) env[row.key.trim()] = row.value
    }
    return { ...form, args, env }
  }

  async function handleSave() {
    setSaving(true)
    setFormError(null)
    try {
      const payload = buildPayload()
      if (editingId) {
        const updated = await updateMcpServer(token, editingId, payload)
        setServers((prev) => prev.map((s) => (s.id === editingId ? updated : s)))
      } else {
        const created = await createMcpServer(token, payload)
        setServers((prev) => [...prev, created])
      }
      cancelForm()
    } catch (err) {
      setFormError(err instanceof Error ? err.message : 'Erro ao guardar')
    } finally {
      setSaving(false)
    }
  }

  async function handleToggle(server: McpServer) {
    try {
      const updated = await updateMcpServer(token, server.id, { enabled: !server.enabled })
      setServers((prev) => prev.map((s) => (s.id === server.id ? updated : s)))
    } catch {
      // silently ignore toggle errors; user can retry
    }
  }

  async function handleDelete(id: string) {
    setDeletingId(id)
    try {
      await deleteMcpServer(token, id)
      setServers((prev) => prev.filter((s) => s.id !== id))
      if (editingId === id) cancelForm()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro ao eliminar')
    } finally {
      setDeletingId(null)
    }
  }

  async function handleExport() {
    setExporting(true)
    try {
      const data = await exportMcpConfig(token)
      setExportJson(JSON.stringify(data, null, 2))
      setShowExport(true)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro ao exportar')
    } finally {
      setExporting(false)
    }
  }

  const isFormOpen = editingId !== null || form.name !== '' || form.command !== ''

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <h1 className={styles.title}>Servidores MCP</h1>
        <p className={styles.sectionDesc}>
          Configure servidores Model Context Protocol (MCP) que o openclaude usará nas sessões de agente.
        </p>
      </div>

      {error && <p className={styles.errorMsg}>{error}</p>}

      {/* Server list */}
      <div className={styles.section}>
        <div className={mcpStyles.sectionHeader}>
          <div>
            <p className={styles.sectionTitle}>Servidores configurados</p>
            <p className={styles.sectionDesc} style={{ margin: 0 }}>
              {servers.length === 0 ? 'Nenhum servidor MCP configurado ainda.' : `${servers.length} servidor(es)`}
            </p>
          </div>
          <div className={mcpStyles.headerActions}>
            <button
              className={mcpStyles.exportBtn}
              onClick={() => void handleExport()}
              disabled={exporting}
            >
              {exporting ? 'Exportando…' : 'Ver JSON'}
            </button>
            <button className={mcpStyles.addBtn} onClick={startCreate}>
              + Adicionar
            </button>
          </div>
        </div>

        {loading ? (
          <p className={mcpStyles.hint}>Carregando…</p>
        ) : servers.length > 0 ? (
          <table className={styles.table}>
            <thead>
              <tr>
                <th>Nome</th>
                <th>Comando</th>
                <th>Args</th>
                <th>Estado</th>
                <th style={{ textAlign: 'right' }}>Ações</th>
              </tr>
            </thead>
            <tbody>
              {servers.map((s) => (
                <tr key={s.id} className={editingId === s.id ? mcpStyles.editingRow : ''}>
                  <td>
                    <span className={mcpStyles.serverName}>{s.name}</span>
                  </td>
                  <td>
                    <code className={mcpStyles.code}>{s.command}</code>
                  </td>
                  <td>
                    <span className={mcpStyles.argsList}>
                      {s.args.length > 0 ? s.args.join(' ') : '—'}
                    </span>
                  </td>
                  <td>
                    <button
                      className={`${mcpStyles.toggleBtn} ${s.enabled ? mcpStyles.toggleBtnOn : mcpStyles.toggleBtnOff}`}
                      onClick={() => void handleToggle(s)}
                      title={s.enabled ? 'Desativar' : 'Ativar'}
                    >
                      {s.enabled ? 'Ativo' : 'Inativo'}
                    </button>
                  </td>
                  <td>
                    <div className={styles.actions}>
                      <button
                        className={styles.actionBtn}
                        onClick={() => startEdit(s)}
                        title="Editar"
                      >
                        ✎
                      </button>
                      <button
                        className={`${styles.actionBtn} ${styles.actionBtnDanger}`}
                        onClick={() => void handleDelete(s.id)}
                        disabled={deletingId === s.id}
                        title="Eliminar"
                      >
                        ✕
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : null}
      </div>

      {/* Add / Edit form */}
      {(isFormOpen || editingId !== null) && (
        <div className={styles.section}>
          <p className={styles.sectionTitle}>
            {editingId ? 'Editar servidor MCP' : 'Novo servidor MCP'}
          </p>

          <div className={styles.form}>
            <div className={styles.formRow}>
              <label className={mcpStyles.label}>
                Nome <span className={mcpStyles.required}>*</span>
                <input
                  className={mcpStyles.input}
                  placeholder="ex: filesystem, github, sqlite"
                  value={form.name}
                  onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                />
              </label>
            </div>

            <div className={styles.formRow}>
              <label className={mcpStyles.label}>
                Comando <span className={mcpStyles.required}>*</span>
                <input
                  className={mcpStyles.input}
                  placeholder="ex: npx, uvx, python, node"
                  value={form.command}
                  onChange={(e) => setForm((f) => ({ ...f, command: e.target.value }))}
                />
              </label>
            </div>

            <div className={styles.formRow}>
              <label className={mcpStyles.label}>
                Args <span className={mcpStyles.hint}>(separados por vírgula)</span>
                <input
                  className={mcpStyles.input}
                  placeholder="ex: -y, @modelcontextprotocol/server-filesystem, /tmp"
                  value={argsText}
                  onChange={(e) => setArgsText(e.target.value)}
                />
              </label>
            </div>

            {/* Env vars */}
            <div>
              <p className={mcpStyles.label}>
                Variáveis de ambiente
                <span className={mcpStyles.hint}> (chave / valor)</span>
              </p>
              <div className={mcpStyles.envList}>
                {envRows.map((row, i) => (
                  <div key={i} className={mcpStyles.envRow}>
                    <input
                      className={mcpStyles.inputSm}
                      placeholder="CHAVE"
                      value={row.key}
                      onChange={(e) => {
                        const next = [...envRows]
                        next[i] = { ...next[i], key: e.target.value }
                        setEnvRows(next)
                      }}
                    />
                    <span className={mcpStyles.envSep}>=</span>
                    <input
                      className={`${mcpStyles.inputSm} ${mcpStyles.inputSmFlex}`}
                      placeholder="valor"
                      value={row.value}
                      onChange={(e) => {
                        const next = [...envRows]
                        next[i] = { ...next[i], value: e.target.value }
                        setEnvRows(next)
                      }}
                    />
                    <button
                      className={mcpStyles.removeEnvBtn}
                      onClick={() => setEnvRows((rows) => rows.filter((_, j) => j !== i))}
                      title="Remover"
                    >
                      ✕
                    </button>
                  </div>
                ))}
                <button
                  className={mcpStyles.addEnvBtn}
                  onClick={() => setEnvRows((rows) => [...rows, { key: '', value: '' }])}
                >
                  + Adicionar variável
                </button>
              </div>
            </div>

            <div className={mcpStyles.enabledRow}>
              <label className={mcpStyles.checkboxLabel}>
                <input
                  type="checkbox"
                  checked={form.enabled ?? true}
                  onChange={(e) => setForm((f) => ({ ...f, enabled: e.target.checked }))}
                />
                Ativo
              </label>
            </div>

            {formError && <p className={styles.errorMsg}>{formError}</p>}

            <div className={mcpStyles.formActions}>
              <button className={mcpStyles.cancelBtn} onClick={cancelForm}>
                Cancelar
              </button>
              <button
                className={mcpStyles.saveBtn}
                onClick={() => void handleSave()}
                disabled={saving || !form.name || !form.command}
              >
                {saving ? 'Guardando…' : editingId ? 'Guardar alterações' : 'Criar servidor'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Export JSON modal */}
      {showExport && (
        <div className={mcpStyles.overlay} onClick={() => setShowExport(false)}>
          <div className={mcpStyles.modal} onClick={(e) => e.stopPropagation()}>
            <div className={mcpStyles.modalHeader}>
              <p className={mcpStyles.modalTitle}>Configuração MCP (openclaude)</p>
              <button className={mcpStyles.modalClose} onClick={() => setShowExport(false)}>
                ✕
              </button>
            </div>
            <pre className={mcpStyles.jsonBlock}>{exportJson}</pre>
          </div>
        </div>
      )}
    </div>
  )
}
