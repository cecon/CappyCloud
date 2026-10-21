import * as React from 'react'
import { X } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Button as ShadButton } from '../button'
import { clean, color, legacyStyle, type LegacyProps, type Size } from './core'

export function Badge({
  className,
  color: tone,
  variant,
  size,
  leftSection,
  rightSection,
  children,
  ...props
}: LegacyProps<HTMLSpanElement> & {
  variant?: string
  size?: Size
  leftSection?: React.ReactNode
  rightSection?: React.ReactNode
}) {
  void variant; void size
  return (
    <span
      className={cn('inline-flex items-center rounded-full border border-border bg-muted px-2 py-0.5 text-xs font-semibold text-muted-foreground', className)}
      style={{ color: color(tone), ...legacyStyle(props) }}
      {...clean(props)}
    >
      {leftSection}
      {children}
      {rightSection}
    </span>
  )
}

export type ActionIconProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: string
  size?: Size
  color?: string
  loading?: boolean
}

export function Button({
  leftSection,
  rightSection,
  loading,
  variant,
  size,
  color: tone,
  className,
  children,
  fullWidth,
  component: Component,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & {
  leftSection?: React.ReactNode
  rightSection?: React.ReactNode
  loading?: boolean
  variant?: string
  size?: Size
  color?: string
  fullWidth?: boolean
  component?: React.ElementType
  to?: string
  href?: string
  [key: string]: unknown
}) {
  const mappedVariant = variant === 'outline' ? 'outline' : variant === 'subtle' || variant === 'light' ? 'secondary' : 'default'
  const Comp = Component ?? ShadButton
  return (
    <Comp
      variant={mappedVariant}
      size={size === 'xs' || size === 'sm' ? 'sm' : size === 'lg' ? 'lg' : 'default'}
      className={cn(fullWidth && 'w-full', className)}
      style={{ color: color(tone) }}
      disabled={loading || props.disabled}
      {...props}
    >
      {loading && <Loader size="xs" />}
      {leftSection}
      {children}
      {rightSection}
    </Comp>
  )
}

export function ActionIcon({ loading, className, children, hiddenFrom, ...props }: ActionIconProps & { hiddenFrom?: string }) {
  void hiddenFrom
  return (
    <button
      type="button"
      className={cn('inline-flex size-9 items-center justify-center rounded-md text-muted-foreground hover:bg-accent hover:text-foreground disabled:opacity-50', className)}
      disabled={loading || props.disabled}
      {...props}
    >
      {loading ? <Loader size="xs" /> : children}
    </button>
  )
}

export function Burger({ opened, onClick, className, hiddenFrom, ...props }: ActionIconProps & { opened?: boolean; hiddenFrom?: string }) {
  void hiddenFrom
  return (
    <ActionIcon className={className} onClick={onClick} aria-pressed={opened} {...props}>
      <span className="material-symbols-outlined text-base">{opened ? 'close' : 'menu'}</span>
    </ActionIcon>
  )
}

export function Loader({ size = 'sm', className, color: tone }: { size?: Size; className?: string; color?: string }) {
  const px = size === 'xs' ? 14 : size === 'lg' ? 28 : 20
  return <span className={cn('inline-block animate-spin rounded-full border-2 border-current border-t-transparent', className)} style={{ width: px, height: px, color: color(tone) }} />
}

export function Alert({
  title,
  children,
  color: tone,
  icon,
  withCloseButton,
  onClose,
  className,
  style,
}: {
  title?: React.ReactNode
  children?: React.ReactNode
  color?: string
  icon?: React.ReactNode
  withCloseButton?: boolean
  onClose?: () => void
  className?: string
  variant?: string
  style?: React.CSSProperties
}) {
  return (
    <div className={cn('rounded-md border border-border bg-card p-3 text-sm text-card-foreground', className)} style={{ borderColor: color(tone), ...style }}>
      <div className="flex gap-2">
        {icon}
        <div className="min-w-0 flex-1">
          {title && <div className="mb-1 font-semibold">{title}</div>}
          <div className="text-muted-foreground">{children}</div>
        </div>
        {withCloseButton && (
          <button type="button" onClick={onClose} className="text-muted-foreground hover:text-foreground">
            <X className="size-4" />
          </button>
        )}
      </div>
    </div>
  )
}
