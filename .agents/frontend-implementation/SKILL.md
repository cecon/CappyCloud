---
name: frontend-implementation
description: Use esta habilidade quando precisar implementar interfaces e componentes no frontend do CappyCloud (React 19 + Mantine 9). Use esta habilidade para criar páginas, componentes reutilizáveis e integrar com a API.
---

# Frontend Implementation — CappyCloud

Este guia define os padrões para desenvolvimento do frontend em `web/src`.

## 1. Tecnologias Core
- **Framework**: React 19 (Vite)
- **UI Kit**: Mantine 9
- **Icons**: Tabler Icons (@tabler/icons-react)
- **Routing**: React Router 7
- **Estilização**: CSS Modules (Vanilla CSS)

## 2. Estrutura de Implementação

### Passo 1: Integração com API (`web/src/api.ts`)
Toda chamada ao backend deve ser centralizada aqui.
- Defina as Interfaces/Types para os dados.
- Use `apiFetch` (wrapper do `fetch` que trata 401).
- Trate erros com `formatApiErrorPayload`.

```typescript
export type MyData = { id: string; name: string };

export async function fetchMyData(token: string): Promise<MyData[]> {
  const res = await apiFetch('/api/my-data', {
    headers: { Authorization: `Bearer ${token}` }
  });
  if (!res.ok) throw new Error('Falha ao carregar dados');
  return res.json();
}
```

### Passo 2: Componentes Reutilizáveis (`web/src/components/`)
- Crie um arquivo `.tsx` para o componente.
- Crie um arquivo `.module.css` para estilos específicos.
- Use componentes do Mantine como base (`Box`, `Flex`, `Stack`, `Text`).

### Passo 3: Páginas (`web/src/pages/`)
- Use `useEffect` para carregar dados iniciais.
- Trate estados de `loading` e `error`.
- Integre com `api.ts` e use o `token` vindo de `getToken()`.

## 3. Padrões de Design e UI
- **Estética IDE**: O projeto segue um tema escuro (Dark Mode) estilo IDE premium ("The Silent Architect").
- **CSS Modules**: Evite estilos inline. Use classes definidas no `.module.css`.
- **Micro-interações**: Use transições suaves (`transition: all 0.2s ease`) e estados de `hover`/`active`.
- **Responsividade**: Use os breakpoints do Mantine ou Media Queries no CSS.

## 4. Gerenciamento de Estado
- **Local**: `useState` para estados simples.
- **Global**: O token é persistido via `api.ts` no `localStorage`.
- **Complexo**: Use `useReducer` ou hooks customizados do Mantine (`useDisclosure`, `useListState`).

## 5. Convenções
- **Nomenclatura**:
  - Componentes: `PascalCase` (ex: `ChatSidebar.tsx`)
  - Funções/Variáveis: `camelCase`
  - Arquivos CSS: `nome_do_componente.module.css`
- **Imports**: Mantenha imports organizados (React → Mantine → Local).
- **TypeScript**: Use tipagem forte para todas as Props e retornos de API.

---
**Regra de Ouro**: O frontend deve parecer "Premium" e "State of the Art". Evite cores básicas e layouts genéricos.

## 6. Ativação de Skills de Qualidade
Após concluir a implementação de componentes ou páginas, você **DEVE** ativar as seguintes habilidades:
1.  **code-review**: Para verificar a qualidade do código React/TS e conformidade com o design system.
2.  **vulnerability-auditor**: Para garantir que não há exposição de tokens ou falhas de segurança no client-side.
