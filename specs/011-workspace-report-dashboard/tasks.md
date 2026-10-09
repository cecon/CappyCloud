# Tasks: Relatório de uso por workspace

**Input**: [spec.md](spec.md), [plan.md](plan.md), [research.md](research.md),
[data-model.md](data-model.md), [contracts/admin-reports.md](contracts/admin-reports.md)

## Phase 1: Setup

- [x] T001 Adicionar `tzdata` em `services/api/requirements.txt`
- [x] T002 Colunas `report_theme_preset` e `report_themes` em `Workspace` (`app/infrastructure/orm_models_workspaces.py`) e migration via `alembic revision` com o seed do proteus

## Phase 2: Foundational

- [x] T003 [P] Domínio de temas: `app/domain/report_themes.py` (normalização sem acento, validação, classificação, modelos `generico` e `nfse-protheus`)
- [x] T004 [P] Port `app/ports/workspace_report.py` (DTOs + ABC `WorkspaceReportRepository`)
- [x] T005 Adapter `app/adapters/secondary/persistence/sqlalchemy_workspace_report_repo.py`
- [x] T006 Fake `tests/fakes_reports.py` exposto pelo `tests/conftest.py`
- [x] T007 Contrato da port contra fake e SQLAlchemy em `tests/adapter/test_workspace_report_repo_contract.py`

## Phase 3: US1 + US4 — Relatório e restrição de acesso (P1) 🎯 MVP

- [x] T008 [US1] Agregação pura em `app/application/use_cases/_workspace_report_metrics.py` (consultas, analistas, médias, semanas ISO, temas, workspaces, consultas)
- [x] T009 [US1][US4] Use cases em `app/application/use_cases/workspace_report.py` (escopo visível, 403/404, período 422, opções)
- [x] T010 [US1] Router `app/adapters/primary/http/admin_reports.py` (`/options`, `/workspace`) e registro no `main.py`
- [x] T011 [P] [US1] Testes unitários da agregação em `tests/unit/test_workspace_report_metrics.py` (fronteiras do período, semana que cruza o ano, divisão por zero, custo nulo)
- [x] T012 [US1][US4] Integração em `tests/integration/test_api_admin_reports.py` (filtros workspace/branch/período, médias, semanas, 403 admin comum, 403 usuário, "Todos" restrito)

## Phase 4: US2 — Temas (P2)

- [x] T013 [P] [US2] Testes unitários em `tests/unit/test_report_themes.py` (amostra real do proteus, acentos, ordem, "Outros", validação)
- [x] T014 [US2] Use cases e rotas `GET/PUT /admin/reports/themes/{workspace_id}` (PUT só super admin) + testes de integração

## Phase 5: US3 — Exportação (P2)

- [x] T015 [US3] `app/adapters/primary/http/_admin_reports_export.py` (XLSX com 5 abas, CSV `;` com BOM) e rota `/workspace/export`
- [x] T016 [US3] Testes de integração da exportação (linhas e totais batem com o JSON, 403 vale também)

## Phase 6: Frontend

- [x] T017 [P] Cliente `web/src/api/reports.ts` (tipos + chamadas + download)
- [x] T018 Componentes `web/src/components/reports/` (filtros, KPIs, tabela de analistas, semanas, temas, consultas, editor de temas)
- [x] T019 Página `web/src/pages/AdminReportsPage.tsx` e página imprimível `web/src/pages/AdminReportPrintPage.tsx` com print CSS
- [x] T020 Rotas em `web/src/App.tsx`, menu em `navigation.ts`, cobertura em `routeCoverage.ts`

## Phase 7: Polish

- [x] T021 Gates: `ruff check`, `ruff format --check`, `mypy app/`, `pytest` (≥ 80%), `npm run lint`, `npm run build`
- [x] T022 Verificação visual da página e da versão imprimível no navegador
- [x] T023 Atualizar `docs/` se houver índice de rotas admin; PR contra `main`

## Dependencies

- T002 → T005; T003, T004 → T005–T009; T009 → T010 → T012/T014/T016.
- Frontend (T017–T020) depende só do contrato.
