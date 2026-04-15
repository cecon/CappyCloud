/**
 * Email com domínio (ex.: nome@mail.com) — evita 422 por formatos que o Pydantic rejeita.
 */
export function isPlausibleEmail(s: string): boolean {
  const t = s.trim()
  return /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(t)
}
