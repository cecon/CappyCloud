import { AlertTriangle } from 'lucide-react'
import { Button } from '@/components/ui/button'

export type CommandConfirmationProps = {
  message: string
  confirmLabel?: string
  cancelLabel?: string
  onConfirm: () => void
  onCancel: () => void
}

export function CommandConfirmation({
  message,
  confirmLabel = 'Executar',
  cancelLabel = 'Cancelar',
  onConfirm,
  onCancel,
}: CommandConfirmationProps) {
  return (
    <div className="flex items-center gap-3 rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-950 dark:border-amber-700 dark:bg-amber-950/30 dark:text-amber-100">
      <AlertTriangle className="size-4 shrink-0" aria-hidden="true" />
      <span className="min-w-0 flex-1">{message}</span>
      <Button type="button" size="sm" variant="outline" onClick={onCancel}>
        {cancelLabel}
      </Button>
      <Button type="button" size="sm" onClick={onConfirm}>
        {confirmLabel}
      </Button>
    </div>
  )
}
