export type ThemeMode = 'light' | 'dark' | 'system'

export const THEME_KEY = 'cappycloud.theme.mode'

export function readTheme(): ThemeMode {
  const value = window.localStorage.getItem(THEME_KEY)
  return value === 'light' || value === 'dark' || value === 'system' ? value : 'dark'
}

export function resolveTheme(mode: ThemeMode): 'light' | 'dark' {
  const systemDark = window.matchMedia('(prefers-color-scheme: dark)').matches
  return mode === 'dark' || (mode === 'system' && systemDark) ? 'dark' : 'light'
}

export function persistTheme(mode: ThemeMode) {
  window.localStorage.setItem(THEME_KEY, mode)
}

export function applyTheme(mode: ThemeMode = readTheme()) {
  const resolved = resolveTheme(mode)
  const root = document.documentElement
  root.classList.toggle('dark', resolved === 'dark')
  root.dataset.theme = resolved
  root.style.colorScheme = resolved
}

export function applyStoredTheme() {
  const mode = readTheme()
  persistTheme(mode)
  applyTheme(mode)
}
