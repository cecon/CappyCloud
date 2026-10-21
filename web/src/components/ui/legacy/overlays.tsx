/* eslint-disable react-refresh/only-export-components */
import * as React from 'react'
import * as DialogPrimitive from '@radix-ui/react-dialog'
import * as DropdownMenuPrimitive from '@radix-ui/react-dropdown-menu'
import { X } from 'lucide-react'
import { cn } from '@/lib/utils'
import { ScrollArea as ShadScrollArea } from '../scroll-area'
import {
  Tabs as ShadTabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from '../tabs'
import { color, overlaySize, unit, type Size } from './core'

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
          className="grid gap-4 overflow-auto rounded-lg border border-border bg-popover p-4 sm:p-6 text-popover-foreground shadow-lg grid-cols-[minmax(0,1fr)]"
          style={{
            position: 'fixed',
            left: '50%',
            top: '50%',
            zIndex: 51,
            width: 'calc(100vw - 2rem)',
            maxWidth: overlaySize(size, '42rem'),
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
          style={{
            width: overlaySize(size, '36rem'),
            minWidth: 'min(20rem, calc(100vw - 1rem))',
            maxWidth: 'calc(100vw - 1rem)',
            boxSizing: 'border-box',
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

// Caixa com rolagem lateral: no celular a tabela rola em vez de cortar as colunas (ações).
const TableRoot = ({ className, ...props }: React.TableHTMLAttributes<HTMLTableElement> & { verticalSpacing?: Size; highlightOnHover?: boolean }) => (
  <div className="w-full min-w-0 max-w-full overflow-x-auto">
    <table className={cn('w-full border-collapse text-sm', className)} {...props} />
  </div>
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
