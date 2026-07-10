---
name: design-system
description: Use esta habilidade para gerar ou evoluir o design system do CappyCloud - tokens, paletas, tipografia, espacamentos e padroes de componentes.
---

# Design System Generator - CappyCloud

Use esta skill para definir tokens, componentes, estados e padroes visuais do
CappyCloud. A base ativa vem do plano Spec Kit da feature.

## 1. Base Ativa

- **Padrao legado**: Mantine 9 + CSS Modules.
- **`007-chat-centered-ui-theme`**: shadcn/ui + Tailwind CSS v4.
- **Primitivos shadcn**: `web/src/components/ui/`.
- **Helper de classes**: `web/src/lib/utils.ts` com `cn`.
- **Tokens globais**: `web/src/index.css`.

Nao deixe dois sistemas visuais permanentes na mesma superficie autenticada. Em
migracoes aprovadas, Mantine e CSS Modules podem existir apenas enquanto a
superficie ainda nao foi migrada.

## 2. Arquitetura De Tokens

### Camada 1 - Primitivos

Defina cores base, tipografia, espacamento, radius e sombras em CSS variables.
No fluxo shadcn/Tailwind, exponha os tokens em `web/src/index.css` e conecte-os
ao tema Tailwind. No fluxo legado, os mesmos valores podem alimentar o tema
Mantine.

### Camada 2 - Semantica

Use aliases que descrevem papel, nao cor:

```css
--surface-base: var(--color-dark-900);
--surface-raised: var(--color-dark-800);
--surface-overlay: var(--color-dark-700);
--border-default: var(--color-dark-500);
--border-focus: var(--accent-primary);
--text-primary: var(--color-dark-050);
--text-secondary: var(--color-dark-200);
--text-muted: var(--color-dark-300);
--accent-primary: var(--color-blue-500);
--status-success: var(--color-green-500);
--status-error: var(--color-red-500);
--status-warning: var(--color-yellow-500);
```

### Camada 3 - Componentes

Mapeie estados de componentes para tokens semanticos. Evite hex hardcoded em
componentes. Estados minimos:

```text
default -> hover -> active/pressed -> focus -> disabled -> loading -> error
```

## 3. Componentes

Para `007-chat-centered-ui-theme`, comece por:

- `button`
- `dropdown-menu`
- `dialog`
- `sheet`
- `tabs`
- `input`
- `textarea`
- `select`
- `badge`
- `card`
- `table`
- `tooltip`
- `scroll-area`
- `skeleton`

Use componentes de composicao em `web/src/components/layout/`,
`web/src/components/chat/` e `web/src/components/admin/` para montar a
experiencia real. Cards devem ter raio maximo de 8px salvo excecao do design
system ativo.

## 4. Identidade Visual

O CappyCloud deve manter a sensacao de ferramenta profissional premium, estilo
IDE: contraste claro, hierarquia discreta, superficies organizadas e acoes
primarias obvias. Evite paletas de uma unica familia de cor e evite depender
de gradientes decorativos para comunicar estrutura.

## 5. Validacao

Antes de considerar o design implementado:

- [ ] Usa tokens semanticos, sem hex hardcoded em componentes
- [ ] Todos os estados interativos existem
- [ ] Contraste de texto normal >= 4.5:1 e foco visivel
- [ ] Dark e light modes permanecem legiveis
- [ ] CSS Modules no fluxo legado, ou Tailwind/tokens no fluxo shadcn aprovado
- [ ] Responsividade validada nos viewports previstos pela feature
- [ ] Nao ha overlap de texto, controles, menus ou compositor de chat
