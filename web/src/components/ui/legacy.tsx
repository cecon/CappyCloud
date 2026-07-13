/* eslint-disable react-refresh/only-export-components */
import * as React from 'react'
import * as DialogPrimitive from '@radix-ui/react-dialog'
import * as DropdownMenuPrimitive from '@radix-ui/react-dropdown-menu'
import { X } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Button as ShadButton } from './button'
import { ScrollArea as ShadScrollArea } from './scroll-area'
import {
  Tabs as ShadTabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from './tabs'

type Size = 'xs' | 'sm' | 'md' | 'lg' | 'xl' | number | string
type LegacyProps<T extends HTMLElement = HTMLDivElement> =
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

function unit(value: Size | undefined): string | number | undefined {
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

function color(value: string | undefined): string | undefined {
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

function legacyStyle<T extends HTMLElement>(props: LegacyProps<T>): React.CSSProperties {
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

function clean<T extends LegacyProps>(props: T) {
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

function gapValue(gap?: Size): string | number | undefined {
  return unit(gap ?? 'md')
}

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
      className={cn('mx-auto w-full px-4', className)}
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
      <span className="material-symbols-rounded text-base">{opened ? 'close' : 'menu'}</span>
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

function fieldId(label?: React.ReactNode) {
  return typeof label === 'string' ? label.toLowerCase().replace(/\W+/g, '-') : undefined
}

function Field({
  label,
  description,
  error,
  children,
}: {
  label?: React.ReactNode
  description?: React.ReactNode
  error?: React.ReactNode
  children: React.ReactNode
}) {
  return (
    <label className="grid gap-1.5 text-sm">
      {label && <span className="font-medium text-foreground">{label}</span>}
      {children}
      {description && <span className="text-xs text-muted-foreground">{description}</span>}
      {error && <span className="text-xs text-destructive">{error}</span>}
    </label>
  )
}

const inputClass = 'h-9 w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring disabled:cursor-not-allowed disabled:opacity-50'

type FieldProps = {
  label?: React.ReactNode
  description?: React.ReactNode
  error?: React.ReactNode
  styles?: unknown
  w?: Size
  mt?: Size
}

export function TextInput({
  label,
  description,
  error,
  className,
  w,
  mt,
  styles,
  size,
  ...props
}: Omit<React.InputHTMLAttributes<HTMLInputElement>, 'size'> & FieldProps & { size?: Size }) {
  void styles; void size
  return (
    <Field label={label} description={description} error={error}>
      <input
        id={fieldId(label)}
        className={cn(inputClass, className)}
        style={{ width: unit(w), marginTop: unit(mt), ...props.style }}
        {...props}
      />
    </Field>
  )
}

export function PasswordInput(props: Omit<React.InputHTMLAttributes<HTMLInputElement>, 'size'> & FieldProps & { size?: Size }) {
  return <TextInput {...props} type="password" />
}

export function Textarea({
  label,
  description,
  error,
  className,
  autosize,
  minRows,
  maxRows,
  styles,
  ...props
}: React.TextareaHTMLAttributes<HTMLTextAreaElement> & FieldProps & { autosize?: boolean; minRows?: number; maxRows?: number }) {
  void autosize; void maxRows; void styles
  return (
    <Field label={label} description={description} error={error}>
      <textarea className={cn(inputClass, 'min-h-24 resize-y', className)} rows={props.rows ?? minRows} {...props} />
    </Field>
  )
}

export function NumberInput({
  label,
  description,
  error,
  onChange,
  value,
  w,
  mt,
  styles,
  size,
  ...props
}: Omit<React.InputHTMLAttributes<HTMLInputElement>, 'onChange' | 'value' | 'size'> & {
  label?: React.ReactNode
  description?: React.ReactNode
  error?: React.ReactNode
  value?: number | string
  onChange?: (value: number | string) => void
  w?: Size
  mt?: Size
  styles?: unknown
  size?: Size
}) {
  void styles; void size
  return (
    <TextInput
      {...props}
      type="number"
      label={label}
      description={description}
      error={error}
      w={w}
      mt={mt}
      value={value ?? ''}
      onChange={(event) => onChange?.(event.currentTarget.value === '' ? '' : Number(event.currentTarget.value))}
    />
  )
}

export function Select({
  label,
  description,
  error,
  data = [],
  value,
  onChange,
  placeholder,
  allowDeselect,
  className,
  w,
  mt,
  styles,
  size,
  leftSection,
  rightSection,
  searchable,
  clearable,
  ...props
}: Omit<React.SelectHTMLAttributes<HTMLSelectElement>, 'onChange' | 'value' | 'size'> & {
  label?: React.ReactNode
  description?: React.ReactNode
  error?: React.ReactNode
  data?: Array<string | { value: string; label: string }>
  value?: string | null
  onChange?: (value: string | null) => void
  allowDeselect?: boolean
  placeholder?: string
  size?: Size
  leftSection?: React.ReactNode
  rightSection?: React.ReactNode
  searchable?: boolean
  clearable?: boolean
  w?: Size
  mt?: Size
  styles?: unknown
}) {
  void allowDeselect; void searchable; void clearable; void styles; void size; void leftSection; void rightSection
  return (
    <Field label={label} description={description} error={error}>
      <select
        className={cn(inputClass, className)}
        style={{ width: unit(w), marginTop: unit(mt), ...props.style }}
        value={value ?? ''}
        onChange={(event) => onChange?.(event.currentTarget.value || null)}
        {...props}
      >
        {placeholder && <option value="">{placeholder}</option>}
        {data.map((item) => {
          const option = typeof item === 'string' ? { value: item, label: item } : item
          return <option key={option.value} value={option.value}>{option.label}</option>
        })}
      </select>
    </Field>
  )
}

export function MultiSelect({
  label,
  description,
  error,
  data = [],
  value = [],
  onChange,
  className,
  placeholder,
  size,
  searchable,
  clearable,
  styles,
  ...props
}: Omit<React.SelectHTMLAttributes<HTMLSelectElement>, 'onChange' | 'value' | 'size'> & {
  label?: React.ReactNode
  description?: React.ReactNode
  error?: React.ReactNode
  data?: Array<string | { value: string; label: string }>
  value?: string[]
  onChange?: (value: string[]) => void
  placeholder?: string
  size?: Size
  searchable?: boolean
  clearable?: boolean
  styles?: unknown
}) {
  void placeholder; void searchable; void clearable; void styles; void size
  return (
    <Field label={label} description={description} error={error}>
      <select
        multiple
        className={cn(inputClass, 'h-32', className)}
        value={value}
        onChange={(event) => onChange?.(Array.from(event.currentTarget.selectedOptions).map((option) => option.value))}
        {...props}
      >
        {data.map((item) => {
          const option = typeof item === 'string' ? { value: item, label: item } : item
          return <option key={option.value} value={option.value}>{option.label}</option>
        })}
      </select>
    </Field>
  )
}

export function Switch({ checked, onChange, label, disabled, size, mt }: { checked?: boolean; onChange?: React.ChangeEventHandler<HTMLInputElement>; label?: React.ReactNode; disabled?: boolean; size?: Size; mt?: Size }) {
  void size
  return (
    <label className="inline-flex items-center gap-2 text-sm text-foreground" style={{ marginTop: unit(mt) }}>
      <input type="checkbox" className="size-4 accent-primary" checked={checked} onChange={onChange} disabled={disabled} />
      {label && <span>{label}</span>}
    </label>
  )
}

export function Checkbox({ checked, onChange, label, disabled }: { checked?: boolean; onChange?: React.ChangeEventHandler<HTMLInputElement>; label?: React.ReactNode; disabled?: boolean }) {
  return <Switch checked={checked} onChange={onChange} label={label} disabled={disabled} />
}

export function Modal({ opened, onClose, title, children, size }: { opened: boolean; onClose: () => void; title?: React.ReactNode; children?: React.ReactNode; size?: Size; centered?: boolean }) {
  return (
    <DialogPrimitive.Root open={opened} onOpenChange={(open) => !open && onClose()}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay
          className="bg-background/80 backdrop-blur-sm"
          style={{
            position: 'fixed',
            inset: 0,
            zIndex: 50,
          }}
        />
        <DialogPrimitive.Content
          className="grid gap-4 overflow-auto rounded-lg border border-border bg-popover p-6 text-popover-foreground shadow-lg"
          style={{
            position: 'fixed',
            left: '50%',
            top: '50%',
            zIndex: 51,
            width: 'calc(100vw - 2rem)',
            maxWidth: unit(size) ?? '42rem',
            maxHeight: 'calc(100dvh - 2rem)',
            transform: 'translate(-50%, -50%)',
          }}
        >
          {title && <DialogPrimitive.Title className="text-lg font-semibold">{title}</DialogPrimitive.Title>}
          {children}
          <DialogPrimitive.Close className="absolute right-4 top-4 text-muted-foreground hover:text-foreground">
            <X className="size-4" />
          </DialogPrimitive.Close>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  )
}

export function Drawer({ opened, onClose, title, children, position = 'right', size }: { opened: boolean; onClose: () => void; title?: React.ReactNode; children?: React.ReactNode; position?: 'right' | 'left'; size?: Size }) {
  return (
    <DialogPrimitive.Root open={opened} onOpenChange={(open) => !open && onClose()}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-background/70 backdrop-blur-sm" />
        <DialogPrimitive.Content
          className={cn('fixed top-0 z-50 flex h-dvh flex-col gap-4 overflow-auto border-border bg-popover p-6 text-popover-foreground shadow-lg', position === 'right' ? 'right-0 border-l' : 'left-0 border-r')}
          style={{ width: unit(size) ?? '36rem', maxWidth: 'calc(100vw - 2rem)' }}
        >
          {title && <DialogPrimitive.Title className="text-lg font-semibold">{title}</DialogPrimitive.Title>}
          {children}
          <DialogPrimitive.Close className="absolute right-4 top-4 text-muted-foreground hover:text-foreground">
            <X className="size-4" />
          </DialogPrimitive.Close>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  )
}

function TabsRoot({ value, defaultValue, onChange, children }: { value?: string; defaultValue?: string; onChange?: (value: string | null) => void; children?: React.ReactNode; keepMounted?: boolean }) {
  return <ShadTabs value={value} defaultValue={defaultValue} onValueChange={(next) => onChange?.(next)}>{children}</ShadTabs>
}

function TabsPanel({ value, children, pt, className }: { value: string; children?: React.ReactNode; pt?: Size; className?: string }) {
  return <TabsContent value={value} className={className} style={{ paddingTop: unit(pt) }}>{children}</TabsContent>
}

export const Tabs = Object.assign(TabsRoot, {
  List: TabsList,
  Tab: ({ value, children }: { value: string; children?: React.ReactNode }) => <TabsTrigger value={value}>{children}</TabsTrigger>,
  Panel: TabsPanel,
})

export const ScrollArea = React.forwardRef<
  HTMLDivElement,
  React.ComponentPropsWithoutRef<typeof ShadScrollArea> & {
    viewportRef?: React.RefObject<HTMLDivElement | null>
    onScrollPositionChange?: () => void
  }
>(({ viewportRef, onScrollPositionChange, onScroll, ...props }, ref) => (
  <ShadScrollArea
    ref={(node) => {
      if (typeof ref === 'function') ref(node)
      else if (ref) ref.current = node
      if (viewportRef) viewportRef.current = node
    }}
    onScroll={(event) => {
      onScroll?.(event)
      onScrollPositionChange?.()
    }}
    {...props}
  />
))
ScrollArea.displayName = 'LegacyScrollArea'

export function Collapse({ in: opened, expanded, children }: { in?: boolean; expanded?: boolean; children?: React.ReactNode }) {
  return (opened ?? expanded) ? <>{children}</> : null
}

export function useDisclosure(initial = false) {
  const [opened, setOpened] = React.useState(initial)
  return [
    opened,
    {
      open: () => setOpened(true),
      close: () => setOpened(false),
      toggle: () => setOpened((current) => !current),
    },
  ] as const
}

const TableRoot = ({ className, ...props }: React.TableHTMLAttributes<HTMLTableElement> & { verticalSpacing?: Size; highlightOnHover?: boolean }) => (
  <table className={cn('w-full border-collapse text-sm', className)} {...props} />
)
const Th = ({ className, ta, w, ...props }: React.ThHTMLAttributes<HTMLTableCellElement> & { ta?: React.CSSProperties['textAlign']; w?: Size }) => (
  <th className={cn('border-b border-border px-3 py-2 text-left font-semibold text-muted-foreground', className)} style={{ textAlign: ta, width: unit(w), ...props.style }} {...props} />
)
const Td = ({ className, ...props }: React.TdHTMLAttributes<HTMLTableCellElement>) => <td className={cn('border-b border-border px-3 py-2 align-top', className)} {...props} />
export const Table = Object.assign(TableRoot, {
  Thead: (props: React.HTMLAttributes<HTMLTableSectionElement>) => <thead {...props} />,
  Tbody: (props: React.HTMLAttributes<HTMLTableSectionElement>) => <tbody {...props} />,
  Tfoot: (props: React.HTMLAttributes<HTMLTableSectionElement>) => <tfoot {...props} />,
  Tr: (props: React.HTMLAttributes<HTMLTableRowElement>) => <tr className={cn('hover:bg-muted/35', props.className)} {...props} />,
  Th,
  Td,
})

export function Tooltip({ label, children }: { label?: React.ReactNode; withArrow?: boolean; children: React.ReactNode }) {
  if (!React.isValidElement(children)) return <>{children}</>
  return React.cloneElement(children as React.ReactElement<{ title?: string }>, { title: typeof label === 'string' ? label : undefined })
}

function MenuRoot({ children }: { children?: React.ReactNode; shadow?: string; position?: string }) {
  return <DropdownMenuPrimitive.Root>{children}</DropdownMenuPrimitive.Root>
}
export const Menu = Object.assign(MenuRoot, {
  Target: (props: React.ComponentPropsWithoutRef<typeof DropdownMenuPrimitive.Trigger>) => (
    <DropdownMenuPrimitive.Trigger asChild {...props} />
  ),
  Dropdown: ({ children }: { children?: React.ReactNode }) => (
    <DropdownMenuPrimitive.Portal>
      <DropdownMenuPrimitive.Content className="z-50 min-w-40 rounded-md border border-border bg-popover p-1 text-popover-foreground shadow-md">
        {children}
      </DropdownMenuPrimitive.Content>
    </DropdownMenuPrimitive.Portal>
  ),
  Item: ({ children, onClick, leftSection, color: tone, disabled }: { children?: React.ReactNode; onClick?: () => void; leftSection?: React.ReactNode; color?: string; disabled?: boolean }) => (
    <DropdownMenuPrimitive.Item
      disabled={disabled}
      onClick={onClick}
      className="flex cursor-pointer items-center gap-2 rounded-sm px-2 py-1.5 text-sm outline-none hover:bg-accent disabled:opacity-50"
      style={{ color: color(tone) }}
    >
      {leftSection}
      {children}
    </DropdownMenuPrimitive.Item>
  ),
  Label: ({ children }: { children?: React.ReactNode }) => <div className="px-2 py-1.5 text-xs font-semibold text-muted-foreground">{children}</div>,
  Divider: () => <DropdownMenuPrimitive.Separator className="my-1 h-px bg-border" />,
})

function TimelineRoot({ children }: { children?: React.ReactNode; active?: number; bulletSize?: number; lineWidth?: number; classNames?: Record<string, string> }) {
  return <div className="grid gap-3 border-l border-border pl-4">{children}</div>
}
function TimelineItem({ title, children, bullet, classNames, ...props }: React.HTMLAttributes<HTMLDivElement> & { title?: React.ReactNode; children?: React.ReactNode; bullet?: React.ReactNode; classNames?: Record<string, string> }) {
  void classNames
  return (
    <div className="relative" {...props}>
      <span className="absolute -left-[1.35rem] top-1 flex size-3 items-center justify-center rounded-full bg-primary text-primary-foreground">{bullet}</span>
      {title && <div className="font-semibold">{title}</div>}
      <div className="text-sm text-muted-foreground">{children}</div>
    </div>
  )
}
export const Timeline = Object.assign(TimelineRoot, { Item: TimelineItem })
