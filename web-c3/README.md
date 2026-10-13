# web-c3

Frontend do CappyCloud no C3Theme, em migração tela a tela
([specs/013-c3theme-frontend](../specs/013-c3theme-frontend/spec.md)). Servido em `/c3/`
ao lado do `web/` até a virada.

## Rodar

Precisa de acesso de leitura ao repositório privado `cecon/C3Theme` (o tema
`@c3theme/ui` é instalado por git, commit fixo em `package.json`).

```bash
pnpm install
pnpm dev          # http://localhost:5175/c3/  (proxy /api → VITE_API_PROXY_TARGET ou :38000)
```

Checks: `pnpm lint`, `pnpm format:check`, `pnpm typecheck`, `pnpm test`, `pnpm build`.

## Como está organizado

- `src/data/`: camada de dados. Reexporta o cliente HTTP do `web/src` (alias
  `@cappy`) enquanto os dois apps convivem. Telas importam só daqui.
- `src/routes/screens.ts`: inventário de telas e nível de acesso (igual ao `web/`).
- `src/routes/ported.ts`: telas já portadas. As outras abrem no `web/`, com a
  mesma sessão (mesmo token no `localStorage`).
- `src/menu-items/`, `src/layout/`: menu e layout do tema (`DashboardLayout`).
- `src/utils/locales/pt.json`: todos os textos, inclusive os `c3.*` do tema.

## Portar uma tela

1. Criar a página em `src/pages/` e registrá-la em `PAGES` (`src/routes/index.tsx`).
2. Incluir o caminho em `PORTED`.
3. Executar o checklist de paridade de `specs/013-c3theme-frontend/data-model.md` e
   marcar o estado da tela lá, no mesmo PR.

Nada do tema (código, arte, textos do fornecedor) entra neste repositório:
`scripts/check_c3theme_leak.py` roda no CI e no hook de push.
