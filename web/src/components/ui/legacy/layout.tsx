import * as React from 'react'
import { cn } from '@/lib/utils'
import { clean, gapValue, legacyStyle, unit, type LegacyProps, type Size } from './core'

export function Stack({
  gap = 'md',
  align,
  justify,
  className,
  ...props
}: LegacyProps & { gap?: Size; align?: string; justify?: string }) {
  return (
    <div
      className={cn('flex flex-col', className)}
      style={{ gap: gapValue(gap), alignItems: align, justifyContent: justify, ...legacyStyle(props) }}
      {...clean(props)}
    />
  )
}

export function Group({
  gap = 'md',
  align = 'center',
  justify,
  wrap,
  className,
  ...props
}: LegacyProps & { gap?: Size; align?: string; justify?: string; wrap?: React.CSSProperties['flexWrap'] }) {
  return (
    <div
      className={cn('flex', className)}
      style={{
        gap: gapValue(gap),
        alignItems: align,
        justifyContent: justify,
        flexWrap: wrap ?? 'wrap',
        ...legacyStyle(props),
      }}
      {...clean(props)}
    />
  )
}

export function Center({ className, ...props }: LegacyProps) {
  return <div className={cn('flex items-center justify-center', className)} style={legacyStyle(props)} {...clean(props)} />
}

export function Container({ className, size, ...props }: LegacyProps & { size?: Size }) {
  return (
    <div
      className={cn('mx-auto w-full px-0 sm:px-4', className)}
      style={{ maxWidth: unit(size) ?? '72rem', ...legacyStyle(props) }}
      {...clean(props)}
    />
  )
}

export function Paper({ className, shadow, withBorder, ...props }: LegacyProps & { shadow?: string; withBorder?: boolean; radius?: Size }) {
  void shadow
  return (
    <div
      className={cn('rounded-md bg-card text-card-foreground', withBorder !== false && 'border border-border', className)}
      style={legacyStyle(props)}
      {...clean(props)}
    />
  )
}

export const Card = Paper

export function SimpleGrid({
  cols = 1,
  spacing = 'md',
  className,
  ...props
}: LegacyProps & { cols?: number | { base?: number; sm?: number; md?: number; lg?: number; xl?: number }; spacing?: Size }) {
  const columnCount = typeof cols === 'number' ? cols : (cols.md ?? cols.base ?? 1)
  return (
    <div
      className={cn('grid', className)}
      style={{ gridTemplateColumns: `repeat(${columnCount}, minmax(0, 1fr))`, gap: unit(spacing), ...legacyStyle(props) }}
      {...clean(props)}
    />
  )
}

export function Divider({ className, label, ...props }: LegacyProps & { label?: React.ReactNode }) {
  return (
    <div className={cn('flex items-center gap-3 text-xs text-muted-foreground', className)} style={legacyStyle(props)} {...clean(props)}>
      <span className="h-px flex-1 bg-border" />
      {label && <span>{label}</span>}
      <span className="h-px flex-1 bg-border" />
    </div>
  )
}

export function Text({
  component,
  span,
  size,
  className,
  lineClamp,
  ...props
}: LegacyProps<HTMLElement> & { component?: React.ElementType; span?: boolean; size?: Size; lineClamp?: number }) {
  const Comp = component ?? (span ? 'span' : 'p')
  return (
    <Comp
      className={cn(size === 'xs' && 'text-xs', size === 'sm' && 'text-sm', size === 'lg' && 'text-lg', className)}
      style={{
        display: lineClamp ? '-webkit-box' : undefined,
        WebkitLineClamp: lineClamp,
        WebkitBoxOrient: lineClamp ? 'vertical' : undefined,
        overflow: lineClamp ? 'hidden' : undefined,
        ...legacyStyle(props),
      }}
      {...clean(props)}
    />
  )
}

export function Title({ order = 2, className, ...props }: LegacyProps<HTMLHeadingElement> & { order?: 1 | 2 | 3 | 4 | 5 | 6 }) {
  const Comp = `h${order}` as React.ElementType
  const sizes = ['text-3xl', 'text-2xl', 'text-xl', 'text-lg', 'text-base', 'text-sm']
  return <Comp className={cn('font-bold leading-tight', sizes[order - 1], className)} style={legacyStyle(props)} {...clean(props)} />
}

export function Code({ className, block, ...props }: LegacyProps<HTMLElement> & { block?: boolean }) {
  const Comp = block ? 'pre' : 'code'
  return <Comp className={cn('rounded bg-muted px-1 py-0.5 font-mono text-sm', block && 'block overflow-auto p-3', className)} style={legacyStyle(props)} {...clean(props)} />
}
