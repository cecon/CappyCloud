import { ShieldQuestion } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'

export type PermissionRequestCardProps = {
  title?: string
  description?: string
  approveLabel?: string
  denyLabel?: string
  onApprove?: () => void
  onDeny?: () => void
}

export function PermissionRequestCard({
  title = 'Permissao solicitada',
  description = 'O agente precisa da sua confirmacao para continuar esta etapa.',
  approveLabel = 'Permitir',
  denyLabel = 'Negar',
  onApprove,
  onDeny,
}: PermissionRequestCardProps) {
  return (
    <Card className="border-warning/30 bg-warning/5">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-sm">
          <ShieldQuestion className="size-4 text-warning" />
          {title}
        </CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent className="pt-0 text-sm text-muted-foreground">
        Revise impacto e escopo antes de aprovar. A autorizacao visual nao substitui os controles do backend.
      </CardContent>
      <CardFooter className="gap-2">
        <Button type="button" size="sm" onClick={onApprove}>{approveLabel}</Button>
        <Button type="button" size="sm" variant="outline" onClick={onDeny}>{denyLabel}</Button>
      </CardFooter>
    </Card>
  )
}
