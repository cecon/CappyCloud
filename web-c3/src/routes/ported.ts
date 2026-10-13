/**
 * Telas já portadas para o web-c3. As demais abrem no frontend atual, com a
 * mesma sessão (contracts/route-map.md, regra 1). Atualize no PR de cada tela,
 * junto com o estado em specs/013-c3theme-frontend/data-model.md.
 */
export const PORTED: ReadonlySet<string> = new Set<string>([]);

/** Endereço da tela: dentro do /c3/ se portada, senão no frontend atual. */
export function screenHref(path: string, origin: string = window.location.origin): string {
  return PORTED.has(path) ? path : `${origin}${path}`;
}
