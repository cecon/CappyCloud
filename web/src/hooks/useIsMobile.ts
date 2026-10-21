import { useSyncExternalStore } from 'react'

/** Mesma largura das regras de celular em chat.module.css. */
export const MOBILE_QUERY = '(max-width: 760px)'

function subscribe(onChange: () => void): () => void {
  const media = window.matchMedia(MOBILE_QUERY)
  media.addEventListener('change', onChange)
  return () => media.removeEventListener('change', onChange)
}

/** True em tela de celular: a barra lateral do chat vira gaveta. */
export function useIsMobile(): boolean {
  return useSyncExternalStore(
    subscribe,
    () => window.matchMedia(MOBILE_QUERY).matches,
    () => false,
  )
}
