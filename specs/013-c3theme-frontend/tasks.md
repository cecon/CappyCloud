# Tasks: Frontend do CappyCloud no C3Theme

**Input**: `specs/013-c3theme-frontend/` (spec, plan, research, data-model, contracts, quickstart)

**Tests**: Vitest só na camada de dados e nas regras de rota/acesso; telas são
validadas pelo checklist de paridade (`data-model.md`).

Cada tela portada é um PR próprio que também marca o estado no inventário.

## Phase 1: Setup

- [ ] T001 Criar `web-c3/` (Vite 8 + React 19 + TS 6) com `package.json`, `tsconfig.json`, `vite.config.ts` (`base: '/c3/'`, porta 5175, proxy `/api`) e `index.html`
- [ ] T002 Adicionar `@c3theme/ui` por git com commit fixo e os peers do tema (MUI 9, Emotion, React Router 8, react-intl, SWR) em `web-c3/package.json`, conforme `contracts/theme-dependency.md`
- [ ] T003 [P] Configurar ESLint (flat) e scripts `lint`, `typecheck`, `build`, `test` em `web-c3/package.json` e `web-c3/eslint.config.js`
- [ ] T004 [P] Adicionar `web-c3` em `.claude/launch.json` e `web-c3/README.md` com o quickstart

## Phase 2: Foundational

- [ ] T005 Criar `web-c3/src/data/` reexportando cliente HTTP, sessão e validações de `web/src` pelo alias `@cappy` (R3), em `web-c3/src/data/index.ts`
- [ ] T006 Criar `web-c3/src/App.tsx` com `C3ThemeProvider` (branding CappyCloud, `storageKey` próprio, `ptBR`), `Locales` e router; `web-c3/src/config.ts`
- [ ] T007 [P] Criar `web-c3/src/utils/locales/pt.json` com os textos `c3.*` do tema e os do app
- [ ] T008 Criar `web-c3/src/routes/ported.ts` e `web-c3/src/routes/index.tsx` com guardas por nível (logado, admin, super admin) e o redirecionamento de tela pendente para o `web/` (contracts/route-map.md, regras 1–4)
- [ ] T009 [P] Testes Vitest das regras de rota e acesso em `web-c3/src/routes/routes.test.ts`
- [ ] T010 Construir `web/` e `web-c3/` na mesma imagem: `web/Dockerfile` (BuildKit secret `c3theme_token` só no `pnpm install` do `web-c3`) e `location /c3/` em `web/nginx.conf`
- [ ] T011 CI: segredo `C3THEME_READ_TOKEN` no build da imagem web (`.github/workflows/container-images.yml`) e lint/typecheck/build do `web-c3` no CI de frontend
- [ ] T012 [P] Verificação de vazamento do tema (R6) em `scripts/check_c3theme_leak.py`, chamada no CI de frontend e no hook local

## Phase 3: User Story 1 - Entrar no CappyCloud com a cara do C3 (P1) 🎯 MVP

**Independent Test**: quickstart.md, "Validar o esqueleto".

- [ ] T013 [US1] Layout: `DashboardLayout` do pacote com header e `NavUser` (e-mail, papel, sair, tema) em `web-c3/src/layout/`
- [ ] T014 [US1] Menu com todas as telas por nível de acesso, abrindo `/c3/` ou o `web/` conforme `ported.ts`, em `web-c3/src/menu-items/index.ts`
- [ ] T015 [US1] Tela de login ligada à API, com erros em português, em `web-c3/src/pages/auth/LoginPage.tsx`
- [ ] T016 [US1] Troca de senha obrigatória em `web-c3/src/pages/auth/ChangePasswordPage.tsx`
- [ ] T017 [US1] Marca CappyCloud (logo e ícone) em `web-c3/src/assets/` e `branding` do `App.tsx`
- [ ] T018 [US1] Redirecionamentos do `web/` replicados em `web-c3/src/routes/index.tsx`
- [ ] T019 [US1] Executar o quickstart do esqueleto e marcar `/login` e `/change-password` em `data-model.md`

## Phase 4: User Story 2 - Chat (P2)

**Independent Test**: checklist de paridade do `/chat`.

- [ ] T020 [US2] Mapear `web/src/pages/ChatPage.tsx` (4.017 linhas) em blocos: lista de conversas, cabeçalho de contexto, timeline, composer, painéis (diff, atividade) e registrar em `specs/013-c3theme-frontend/chat-breakdown.md`
- [ ] T021 [US2] Extrair a lógica do chat sem UI (estado da conversa, streaming, comandos) para hooks reaproveitáveis em `web/src/hooks/` sem mudar o comportamento do `web/`
- [ ] T022 [P] [US2] Lista e busca de conversas, arquivadas, nova conversa em `web-c3/src/pages/chat/ConversationList.tsx`
- [ ] T023 [P] [US2] Seletores de workspace/repositório e modelo em `web-c3/src/pages/chat/ContextBar.tsx`
- [ ] T024 [US2] Timeline com mensagens, passos do agente, subagentes e custo em `web-c3/src/pages/chat/Timeline.tsx`
- [ ] T025 [US2] Composer com anexos, comandos `/`, chamado obrigatório e modo de permissão em `web-c3/src/pages/chat/Composer.tsx`
- [ ] T026 [US2] Pedidos de permissão e perguntas do agente em `web-c3/src/pages/chat/ActionRequired.tsx`
- [ ] T027 [US2] Diff e atividade da conversa em `web-c3/src/pages/chat/SidePanels.tsx`
- [ ] T028 [US2] Página `web-c3/src/pages/chat/ChatPage.tsx` juntando os blocos; marcar `/chat` em `ported.ts` e `data-model.md`

## Phase 5: User Story 3 - Telas do usuário (P3)

- [ ] T029 [P] [US3] `/skills` em `web-c3/src/pages/SkillsPage.tsx`
- [ ] T030 [P] [US3] `/runs` em `web-c3/src/pages/RunsPage.tsx`
- [ ] T031 [P] [US3] `/mcp` em `web-c3/src/pages/McpServerPage.tsx`
- [ ] T032 [P] [US3] `/analytics` em `web-c3/src/pages/AnalyticsPage.tsx`
- [ ] T033 [P] [US3] `/settings` (super admin) em `web-c3/src/pages/SettingsPage.tsx`

## Phase 6: User Story 4 - Administração (P4)

- [ ] T034 [P] [US4] `/admin` em `web-c3/src/pages/admin/DashboardPage.tsx`
- [ ] T035 [P] [US4] `/admin/conversations` em `web-c3/src/pages/admin/ConversationsPage.tsx`
- [ ] T036 [P] [US4] `/admin/reports` e `/admin/reports/print` em `web-c3/src/pages/admin/reports/`
- [ ] T037 [P] [US4] `/admin/users` em `web-c3/src/pages/admin/UsersPage.tsx`
- [ ] T038 [P] [US4] `/admin/sandboxes` em `web-c3/src/pages/admin/SandboxesPage.tsx`
- [ ] T039 [P] [US4] `/admin/models` em `web-c3/src/pages/admin/ModelsPage.tsx`
- [ ] T040 [P] [US4] `/admin/providers` em `web-c3/src/pages/admin/ProvidersPage.tsx`
- [ ] T041 [P] [US4] `/admin/workspaces` (super admin) em `web-c3/src/pages/admin/WorkspacesPage.tsx`
- [ ] T042 [P] [US4] `/admin/repositories` (super admin) em `web-c3/src/pages/admin/RepositoriesPage.tsx`
- [ ] T043 [P] [US4] `/admin/skills-global` (super admin) em `web-c3/src/pages/admin/GlobalSkillsPage.tsx`

## Phase 7: User Story 5 - Virada (P5)

- [ ] T044 [US5] Conferir todas as telas com estado `paridade` em `data-model.md`
- [ ] T045 [US5] Mover a camada de dados de `web/src` para `web-c3/src/data/` e remover o alias `@cappy`
- [ ] T046 [US5] Servir `web-c3` em `/` (`base: '/'`), redirecionar `/c3/*` → `/*` em `web/nginx.conf`
- [ ] T047 [US5] Remover `web/` do build, do CI e do repositório; renomear `web-c3/` para `web/`
- [ ] T048 [US5] Atualizar `.agents/skills/design-system`, `frontend-implementation` e `ux-design` e o princípio VI da constituição para o sistema de design novo

## Dependencies

- Phase 1 → Phase 2 → US1. US2–US4 dependem de US1 e são independentes entre si.
- US5 depende de todas as telas em `paridade`.
- T010/T011 precisam do segredo `C3THEME_READ_TOKEN` criado pelo dono do repositório do tema.

## MVP

Phases 1–3 (esqueleto + login) num primeiro PR: valida tema, sessão
compartilhada, build e publicação em `/c3/` sem afetar o `web/`.
