import { useId, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { cn } from '@/lib/utils'
import chatStyles from './chat.module.css'

type MarkdownEditorProps = {
  label: string
  value: string
  onChange: (value: string) => void
  description?: string
  placeholder?: string
  required?: boolean
  rows?: number
  /** Aviso de tamanho: acima disso o agente recebe o texto cortado. */
  softLimit?: number
}

/** Campo de markdown com abas Escrever / Visualizar e contador de caracteres. */
export function MarkdownEditor({
  label,
  value,
  onChange,
  description,
  placeholder,
  required,
  rows = 14,
  softLimit,
}: MarkdownEditorProps) {
  const [tab, setTab] = useState<'write' | 'preview'>('write')
  const id = useId()
  const over = softLimit !== undefined && value.length > softLimit

  return (
    <div className="flex flex-col gap-1.5 text-sm">
      <div className="flex items-end justify-between gap-2">
        <label htmlFor={id} className="font-medium">
          {label}
          {required && <span className="text-destructive"> *</span>}
        </label>
        <div role="tablist" aria-label={`${label}: modo`} className="flex rounded-md border border-border p-0.5 text-xs">
          {(['write', 'preview'] as const).map((mode) => (
            <button
              key={mode}
              type="button"
              role="tab"
              aria-selected={tab === mode}
              onClick={() => setTab(mode)}
              className={cn(
                'rounded px-2.5 py-1 transition-colors',
                tab === mode ? 'bg-secondary font-semibold text-foreground' : 'text-muted-foreground hover:text-foreground',
              )}
            >
              {mode === 'write' ? 'Escrever' : 'Visualizar'}
            </button>
          ))}
        </div>
      </div>
      {description && <p className="text-xs text-muted-foreground">{description}</p>}
      {tab === 'write' ? (
        <textarea
          id={id}
          className="min-h-40 w-full resize-y rounded-md border border-input bg-background px-3 py-2 font-mono text-[13px] leading-5 outline-none focus-visible:ring-2 focus-visible:ring-ring"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          rows={rows}
          required={required}
          spellCheck={false}
        />
      ) : (
        <div
          className={cn(chatStyles.markdownBody, 'min-h-40 overflow-auto rounded-md border border-border bg-card px-4 py-3')}
          style={{ maxHeight: `${rows * 1.6}rem` }}
        >
          {value.trim() ? (
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{value}</ReactMarkdown>
          ) : (
            <p className="text-muted-foreground">Nada para visualizar ainda.</p>
          )}
        </div>
      )}
      <p className={cn('text-right text-xs', over ? 'text-destructive' : 'text-muted-foreground')}>
        {value.length.toLocaleString('pt-BR')}
        {softLimit !== undefined && ` / ${softLimit.toLocaleString('pt-BR')}`} caracteres
        {over && ' — o agente recebe só o começo'}
      </p>
    </div>
  )
}
