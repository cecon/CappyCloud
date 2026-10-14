import * as React from 'react'

export type Size = 'xs' | 'sm' | 'md' | 'lg' | 'xl' | number | string
export type LegacyProps<T extends HTMLElement = HTMLDivElement> =
  React.HTMLAttributes<T> & {
    c?: string
    color?: string
    bg?: string
    p?: Size
    px?: Size
    py?: Size
    pt?: Size
    pb?: Size
    mt?: Size
    mb?: Size
    ml?: Size
    mr?: Size
    w?: Size
    maw?: Size
    miw?: Size
    h?: Size
    mih?: Size
    ff?: string
    fw?: number | string
    fs?: React.CSSProperties['fontStyle']
    lh?: React.CSSProperties['lineHeight']
    ta?: React.CSSProperties['textAlign']
    tt?: React.CSSProperties['textTransform']
    grow?: boolean
    classNames?: Record<string, string>
  }

export function unit(value: Size | undefined): string | number | undefined {
  if (value == null) return undefined
  if (typeof value === 'number') return value
  const spacing: Record<string, string> = {
    xs: '0.5rem',
    sm: '0.75rem',
    md: '1rem',
    lg: '1.25rem',
    xl: '1.5rem',
  }
  return spacing[value] ?? value
}

export function overlaySize(value: Size | undefined, fallback: string): string | number {
  if (value == null) return fallback
  if (typeof value === 'number') return value
  const sizes: Record<string, string> = {
    xs: '20rem',
    sm: '24rem',
    md: '32rem',
    lg: '44rem',
    xl: '60rem',
  }
  return sizes[value] ?? value
}

export function color(value: string | undefined): string | undefined {
  if (!value) return undefined
  const map: Record<string, string> = {
    dimmed: 'var(--muted-foreground)',
    red: 'var(--destructive)',
    green: 'var(--success)',
    yellow: 'var(--warning)',
    gray: 'var(--muted-foreground)',
    blue: 'var(--primary)',
    grape: 'var(--primary)',
  }
  return map[value] ?? value
}

export function legacyStyle<T extends HTMLElement>(props: LegacyProps<T>): React.CSSProperties {
  return {
    color: color(props.c ?? props.color),
    background: color(props.bg),
    padding: unit(props.p),
    paddingInline: unit(props.px),
    paddingBlock: unit(props.py),
    paddingTop: unit(props.pt),
    paddingBottom: unit(props.pb),
    marginTop: unit(props.mt),
    marginBottom: unit(props.mb),
    marginLeft: unit(props.ml),
    marginRight: unit(props.mr),
    width: unit(props.w),
    maxWidth: unit(props.maw),
    minWidth: unit(props.miw),
    height: unit(props.h),
    minHeight: unit(props.mih),
    fontFamily: props.ff,
    fontWeight: props.fw,
    fontStyle: props.fs,
    lineHeight: props.lh,
    textAlign: props.ta,
    textTransform: props.tt,
    flex: props.grow ? 1 : undefined,
    ...props.style,
  }
}

export function clean<T extends LegacyProps>(props: T) {
  const {
    c, color: _color, bg, p, px, py, pt, pb, mt, mb, ml, mr, w, maw, miw, h, mih,
    ff, fw, fs, lh, ta, tt, grow, classNames,
    ...rest
  } = props
  void c; void _color; void bg; void p; void px; void py; void pt; void pb; void mt
  void mb; void ml; void mr; void w; void maw; void miw; void h; void mih
  void ff; void fw; void fs; void lh; void ta; void tt; void grow; void classNames
  return rest
}

export function gapValue(gap?: Size): string | number | undefined {
  return unit(gap ?? 'md')
}
