import markUrl from '@/assets/cappycloud-mark.png'
import { cn } from '@/lib/utils'

export function BrandMark({ className }: { className?: string }) {
  return (
    <img
      src={markUrl}
      alt=""
      className={cn('size-9 rounded-md object-contain', className)}
      aria-hidden="true"
    />
  )
}
