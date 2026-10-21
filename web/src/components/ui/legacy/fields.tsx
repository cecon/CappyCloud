import * as React from 'react'
import { cn } from '@/lib/utils'
import { unit, type Size } from './core'

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
