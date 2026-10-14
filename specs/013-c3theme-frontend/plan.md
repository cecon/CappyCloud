# Implementation Plan: Frontend do CappyCloud no C3Theme

**Branch**: `013-c3theme-frontend` | **Date**: 2026-10-13 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/013-c3theme-frontend/spec.md`

## Summary

Criar um segundo app de frontend, `web-c3/`, com a estrutura do seed do
C3Theme e o tema/layout do pacote privado `@c3theme/ui`, servido em `/c3/` no
mesmo domínio e na mesma imagem nginx do `web/` atual. As telas são portadas em
ordem de prioridade (esqueleto e login, chat, telas do usuário, administração).
Com paridade em todas, `web-c3` assume `/`, o `web/` é removido e as skills de
frontend passam a descrever o sistema novo. Nenhuma mudança de API.

## Technical Context

**Language/Version**: TypeScript 6, React 19 (mesma versão do `web/`).

**Primary Dependencies**: `@c3theme/ui` (repositório privado `cecon/C3Theme`,
instalado por git com commit fixo e subdiretório), MUI 9 (+ MUI X 9), Emotion,
React Router 8, react-intl, SWR, Vite 8. Pacotes de peer do tema seguem as
versões do seed.

**Storage**: N/A no frontend; sessão por token no `localStorage` (mesma chave do
`web/`, então a sessão vale nos dois apps).

**Testing**: `pnpm --dir web-c3 lint`, `typecheck`, `build` e Vitest para a
camada de dados; checklist de paridade por tela (`data-model.md`); smoke manual
pelo `quickstart.md`. Os gates do `web/` continuam até a remoção.

**Target Platform**: navegador; imagem `cappycloud-web` (nginx) servindo `web/`
em `/` e `web-c3/` em `/c3/`.

**Project Type**: frontend.

**Performance Goals**: tempo até a primeira resposta do chat igual ao do `web/`
(SC-003); carregamento inicial do `/c3/` com code splitting por rota.

**Constraints**: nenhum arquivo do tema nem arte do Able Pro no repositório
público (SC-004); build falha de forma explícita sem acesso ao pacote (FR-011).

**Scale/Scope**: 19 telas e 5 redirecionamentos (ver `data-model.md`), cerca de 107 componentes no
`web/` a serem substituídos.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] Non-trivial change has a spec, plan, and task breakdown — esta pasta.
- [x] Backend business rules stay in use cases — sem mudança de backend.
- [x] External systems behind ports/adapters — a camada de dados do `web-c3`
      reaproveita o cliente HTTP do `web/` (`src/api.ts`), sem acoplar telas à
      API.
- [x] Security/authorization explicit — mesmas regras do `web/`; rotas admin
      fechadas por papel (FR-003); token do CI só como segredo (RC-004).
- [x] Runtime context dynamic — modelo, workspace, custo continuam vindo da API.
- [x] Required gates planned — lint/typecheck/build do `web-c3` no CI de
      frontend e no hook local; gates do `web/` mantidos até a remoção.
- [x] Evidence requirements — N/A (sem resposta do agente nova).
- [x] Sandbox/worktree/Git behavior — N/A.
- [x] Princípio VI (troca de sistema de design): spec, plano e tarefas aprovam a
      troca; tarefas de migração e validação para cada tela; convivência
      temporária `web/` + `web-c3/` com fim definido (US5, SC-005); skills de
      frontend atualizadas na virada.

Re-check pós-design: sem violações.

## Project Structure

### Documentation (this feature)

```text
specs/013-c3theme-frontend/
├── plan.md
├── research.md
├── data-model.md        # inventário de telas e estado de paridade
├── quickstart.md
├── contracts/
│   ├── route-map.md     # rota do web/ → rota do web-c3/
│   └── theme-dependency.md
└── tasks.md             # /speckit-tasks
```

### Source Code (repository root)

```text
web-c3/                      # app novo (estrutura do seed, código do CappyCloud)
├── package.json             # @c3theme/ui via git, commit fixo
├── vite.config.ts           # base '/c3/', alias @cappy -> ../web/src (só dados)
├── index.html
└── src/
    ├── App.tsx              # C3ThemeProvider + Locales + router
    ├── config.ts            # APP_NAME, rota inicial, defaultConfig
    ├── data/                # reexporta api/validation/hooks de dados do web/
    ├── menu-items/          # menu com todas as telas, por papel
    ├── routes/              # rotas protegidas/abertas, lazy por tela
    ├── layout/              # DashboardLayout do pacote + header/NavUser próprios
    ├── pages/               # telas portadas
    └── utils/locales/pt.json
web/                         # app atual, até a virada
web/Dockerfile               # passa a construir web/ e web-c3/
web/nginx.conf               # + location /c3/
.github/workflows/           # segredo do tema no build da imagem e no CI de frontend
.agents/skills/              # design-system, frontend-implementation, ux-design (na virada)
```

**Structure Decision**: app separado em `web-c3/` (spec: app novo ao lado),
mesma imagem e mesmo domínio para compartilhar sessão sem rota nova no Traefik.
Na virada, `web-c3/` vira o app servido em `/` e `web/` é apagado; renomear a
pasta para `web/` fica como última tarefa.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Dois apps de frontend durante a migração | Portar 20 telas sem deixar o produto incompleto | Substituir `web/` direto deixaria telas sem equivalente em produção |
| Dependência git privada no build | O tema não pode ir para o repositório público | Copiar o pacote publicaria código do Able Pro |
