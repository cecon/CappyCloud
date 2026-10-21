export type FormState = {
  id: string | null
  name: string
  command: string
  args: string
  envEntries: { key: string; value: string }[]
  enabled: boolean
}

export const EMPTY_FORM: FormState = {
  id: null,
  name: '',
  command: '',
  args: '',
  envEntries: [{ key: '', value: '' }],
  enabled: true,
}

export function envEntriesToRecord(entries: { key: string; value: string }[]): Record<string, string> {
  const out: Record<string, string> = {}
  for (const { key, value } of entries) {
    const k = key.trim()
    if (k) out[k] = value
  }
  return out
}

export function envRecordToEntries(env: Record<string, string>): { key: string; value: string }[] {
  const items = Object.entries(env).map(([key, value]) => ({ key, value }))
  return items.length === 0 ? [{ key: '', value: '' }] : items
}

export function parseArgs(text: string): string[] {
  return text
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
}
