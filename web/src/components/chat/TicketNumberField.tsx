import type React from 'react'

type TicketNumberFieldProps = {
  value: string
  onChange: (value: string) => void
  /** Enter com número preenchido: segue para o campo da mensagem. */
  onDone: () => void
  inputRef: React.RefObject<HTMLInputElement | null>
  missing: boolean
  disabled?: boolean
}

/**
 * Número do chamado da conversa nova (workspace que exige). Pensado para uso
 * sem mouse: Enter com o número preenchido passa para a mensagem.
 */
export function TicketNumberField({ value, onChange, onDone, inputRef, missing, disabled }: TicketNumberFieldProps) {
  return (
    <label className="flex items-center gap-2 border-b border-border px-3 py-2 text-sm">
      <span className="shrink-0 font-medium text-muted-foreground">Nº do chamado</span>
      <input
        ref={inputRef}
        className="min-w-0 flex-1 bg-transparent font-mono text-foreground outline-none placeholder:text-muted-foreground/60"
        placeholder="obrigatório neste workspace (Enter para continuar)"
        value={value}
        maxLength={64}
        inputMode="text"
        autoComplete="off"
        aria-invalid={missing}
        aria-describedby={missing ? 'ticket-number-hint' : undefined}
        disabled={disabled}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e) => {
          if (e.key !== 'Enter') return
          e.preventDefault()
          if (value.trim()) onDone()
        }}
      />
      {missing && (
        <span id="ticket-number-hint" className="shrink-0 text-xs text-destructive">
          informe para enviar
        </span>
      )}
    </label>
  )
}
