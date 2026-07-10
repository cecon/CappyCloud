import type { MouseEventHandler, ReactNode } from 'react'
import { ActionIcon, Group, Table, Tooltip, type ActionIconProps } from '@/components/ui/legacy'

type ActionsHeaderProps = {
  width?: number
  label?: string
}

type ActionsCellProps = {
  children: ReactNode
}

type RowActionIconProps = Omit<ActionIconProps, 'aria-label' | 'children' | 'title'> & {
  children: ReactNode
  label: string
  onClick?: MouseEventHandler<HTMLButtonElement>
}

export function ActionsHeader({ width = 120, label = 'Ações' }: ActionsHeaderProps) {
  return (
    <Table.Th ta="right" w={width}>
      {label}
    </Table.Th>
  )
}

export function ActionsCell({ children }: ActionsCellProps) {
  return (
    <Table.Td>
      <Group gap={6} justify="flex-end" wrap="nowrap">
        {children}
      </Group>
    </Table.Td>
  )
}

export function RowActionIcon({
  children,
  label,
  size = 'lg',
  variant = 'subtle',
  ...props
}: RowActionIconProps) {
  return (
    <Tooltip label={label} withArrow>
      <ActionIcon aria-label={label} title={label} size={size} variant={variant} {...props}>
        {children}
      </ActionIcon>
    </Tooltip>
  )
}
