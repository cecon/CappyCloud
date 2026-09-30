import { useEffect, useRef } from 'react'

/** Nada focado (ou só o corpo da página): digitar deve cair num campo. */
function nothingFocused(): boolean {
  const active = document.activeElement
  return !active || active === document.body || active === document.documentElement
}

/**
 * Uso sem mouse: com nada focado, digitar ou apertar Enter leva ao campo que
 * `getTarget` indicar (o foco muda antes da tecla, então o caractere entra nele).
 */
export function useTypeToFocus(getTarget: () => HTMLElement | null, enabled = true) {
  const targetRef = useRef(getTarget)
  useEffect(() => {
    targetRef.current = getTarget
  })

  useEffect(() => {
    if (!enabled) return
    function onKeyDown(e: KeyboardEvent) {
      if (e.defaultPrevented || e.ctrlKey || e.metaKey || e.altKey || e.isComposing) return
      if (!nothingFocused()) return
      const typing = e.key.length === 1
      if (!typing && e.key !== 'Enter') return
      const target = targetRef.current()
      if (!target || (target as HTMLInputElement).disabled) return
      target.focus()
      // Enter só leva ao campo; não envia nada.
      if (e.key === 'Enter') e.preventDefault()
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [enabled])
}
