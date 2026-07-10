---
name: frontend-implementation
description: Use esta habilidade quando precisar implementar interfaces e componentes no frontend do CappyCloud. O padrao legado e React 19 + Mantine 9, mas features com Spec Kit aprovado podem adotar outro design system, como shadcn/ui + Tailwind.
---

# Frontend Implementation - CappyCloud

Este guia define os padroes para desenvolvimento do frontend em `web/src`.

## 1. Tecnologias Core

- **Framework**: React 19 (Vite)
- **UI Kit padrao legado**: Mantine 9, salvo quando o Spec Kit da feature aprovar outra base
- **UI Kit aprovado para `007-chat-centered-ui-theme`**: shadcn/ui com Tailwind CSS v4
- **Icons padrao legado**: Tabler Icons (`@tabler/icons-react`)
- **Icons para `007-chat-centered-ui-theme`**: `lucide-react`
- **Routing**: React Router 7
- **Estilizacao padrao legado**: CSS Modules (Vanilla CSS)
- **Estilizacao para shadcn/Tailwind aprovado**: tokens CSS em `web/src/index.css`, utilitarios Tailwind e primitivos em `web/src/components/ui/`

Use a base registrada no plano Spec Kit ativo. Nao misture Mantine e shadcn/ui
na mesma superficie autenticada depois que a migracao daquela superficie estiver
concluida.

## 2. Estrutura de Implementacao

### Passo 1: Integracao com API (`web/src/api.ts`)

Toda chamada ao backend deve ser centralizada aqui.

- Defina as interfaces/types para os dados.
- Use `apiFetch` (wrapper do `fetch` que trata 401).
- Trate erros com `formatApiErrorPayload`.

```typescript
export type MyData = { id: string; name: string };

export async function fetchMyData(token: string): Promise<MyData[]> {
  const res = await apiFetch('/api/my-data', {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error('Falha ao carregar dados');
  return res.json();
}
```

### Passo 2: Componentes Reutilizaveis (`web/src/components/`)

- Crie um arquivo `.tsx` para o componente.
- No fluxo legado, crie `.module.css` para estilos especificos e use Mantine como base (`Box`, `Flex`, `Stack`, `Text`).
- No fluxo shadcn/Tailwind aprovado, componha primitivos de `web/src/components/ui/`, use `cn` de `web/src/lib/utils.ts`, tokens semanticos de `web/src/index.css` e classes Tailwind sem cores hardcoded.

### Passo 3: Paginas (`web/src/pages/`)

- Use `useEffect` para carregar dados iniciais.
- Trate estados de `loading` e `error`.
- Integre com `api.ts` e use o `token` vindo de `getToken()`.

## 3. Padroes de Design e UI

- **Estetica IDE**: O projeto segue um tema escuro estilo IDE premium ("The Silent Architect").
- **CSS Modules**: use no fluxo legado Mantine; em migracoes shadcn/Tailwind, remova CSS Modules obsoletos apos validar que nao sao mais importados.
- **Micro-interacoes**: Use transicoes suaves (`transition: all 0.2s ease`) e estados de `hover`/`active`.
- **Responsividade**: Use os breakpoints do Mantine no fluxo legado ou utilitarios Tailwind/CSS responsivo no fluxo shadcn/Tailwind aprovado.

## 4. Gerenciamento de Estado

- **Local**: `useState` para estados simples.
- **Global**: O token e persistido via `api.ts` no `localStorage`.
- **Complexo**: Use `useReducer`; hooks Mantine (`useDisclosure`, `useListState`) sao aceitaveis apenas em superficies ainda nao migradas.

## 5. Convencoes

- **Nomenclatura**:
  - Componentes: `PascalCase` (ex: `ChatSidebar.tsx`)
  - Funcoes/variaveis: `camelCase`
  - Arquivos CSS: `nome_do_componente.module.css` no fluxo legado; componentes shadcn em `components/ui`
- **Imports**: Mantenha imports organizados (React -> UI kit ativo -> local).
- **TypeScript**: Use tipagem forte para todas as props e retornos de API.

---

**Regra de ouro**: O frontend deve parecer premium e moderno. Evite cores basicas,
layouts genericos e estilos fora dos tokens do design system ativo.

## 6. Ativacao de Skills de Qualidade

Apos concluir a implementacao de componentes ou paginas, voce DEVE ativar:

1. **code-review**: Para verificar qualidade do codigo React/TS e conformidade com o design system.
2. **vulnerability-auditor**: Para garantir que nao ha exposicao de tokens ou falhas de seguranca no client-side.
