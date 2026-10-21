import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Textarea } from '@/components/ui/textarea'
import { errorToUserMessage, getToken } from '../../api'
import { type ThemeConfig, type ThemeRule, fetchReportThemes, updateReportThemes } from '../../reportsApi'

type Props = {
  workspaceId: string
  workspaceName: string
  open: boolean
  onOpenChange: (open: boolean) => void
  onSaved: () => void
}

/** Super admin: escolhe o modelo de temas do workspace ou grava regras próprias em JSON. */
export function ThemeRulesDialog({ workspaceId, workspaceName, open, onOpenChange, onSaved }: Props) {
  const [config, setConfig] = useState<ThemeConfig | null>(null)
  const [preset, setPreset] = useState('generico')
  const [json, setJson] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    const token = getToken()
    if (!open || !token) return
    setError(null)
    fetchReportThemes(token, workspaceId)
      .then((cfg) => {
        setConfig(cfg)
        setPreset(cfg.preset ?? 'generico')
        setJson(JSON.stringify(cfg.rules, null, 2))
      })
      .catch((err) => setError(errorToUserMessage(err)))
  }, [open, workspaceId])

  async function save(body: { preset: string | null; rules: ThemeRule[] | null }) {
    const token = getToken()
    if (!token) return
    setSaving(true)
    setError(null)
    try {
      await updateReportThemes(token, workspaceId, body)
      onSaved()
      onOpenChange(false)
    } catch (err) {
      setError(errorToUserMessage(err))
    } finally {
      setSaving(false)
    }
  }

  function saveCustom() {
    let rules: ThemeRule[]
    try {
      rules = JSON.parse(json) as ThemeRule[]
    } catch {
      setError('JSON inválido. Confira vírgulas, aspas e colchetes.')
      return
    }
    void save({ preset, rules })
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl">
        <DialogHeader>
          <DialogTitle>Temas do relatório · {workspaceName}</DialogTitle>
          <DialogDescription>
            Cada tema tem expressões regulares aplicadas ao título e à primeira pergunta, sem diferença de
            maiúsculas e acentos. O primeiro tema que casar vence; o resto vai para "Outros".
          </DialogDescription>
        </DialogHeader>
        <div className="flex flex-wrap items-end gap-2">
          <label className="grid gap-1 text-xs font-medium text-muted-foreground">
            Modelo pronto
            <select
              className="h-9 rounded-md border border-input bg-background px-3 text-sm"
              value={preset}
              onChange={(e) => setPreset(e.target.value)}
            >
              {config?.presets.map((p) => (
                <option key={p.key} value={p.key}>
                  {p.label}
                </option>
              ))}
            </select>
          </label>
          <Button variant="outline" disabled={saving || !config} onClick={() => void save({ preset, rules: null })}>
            Usar o modelo (descartar regras próprias)
          </Button>
          {config && (
            <span className="text-xs text-muted-foreground">
              Em vigor: {config.custom ? 'regras próprias' : `modelo ${config.preset}`}
            </span>
          )}
        </div>
        <Textarea
          aria-label="Regras em JSON"
          className="h-80 font-mono text-xs"
          spellCheck={false}
          value={json}
          onChange={(e) => setJson(e.target.value)}
        />
        {error && <p className="text-sm text-destructive">{error}</p>}
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancelar
          </Button>
          <Button disabled={saving || !config} onClick={saveCustom}>
            Salvar regras próprias
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
