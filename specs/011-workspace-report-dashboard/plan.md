# Implementation Plan: Relatório de uso por workspace

**Branch**: `claude/amazing-poitras-1dc8f1` | **Date**: 2026-10-09 | **Spec**: [spec.md](spec.md)

## Summary

Nova página Admin → Relatórios com filtros de workspace, branch e período,
métricas de consultas, analistas, custo (só `messages.cost_usd`), evolução por
semana (blocos de 7 dias) e distribuição por tema, no formato do slide da Diretoria e com R$ pela PTAX, exportação XLSX/CSV e versão imprimível.
O cálculo vive num use case puro sobre uma port de leitura; o tema sai de
regras regex determinísticas por workspace (modelo pronto ou regras próprias),
com "Outros" de reserva. Admin comum só vê os workspaces que tem em
`user_workspace_access`.

## Technical Context

**Language/Version**: Python 3.12 (FastAPI, SQLAlchemy 2 async); TypeScript +
React 19 (Vite, Tailwind/shadcn).
**Primary Dependencies**: openpyxl (já no `requirements.txt`) para XLSX;
`tzdata` (novo, puro Python) para garantir `America/Sao_Paulo` no container.
**Storage**: Postgres; duas colunas novas em `workspaces`
(`report_theme_preset`, `report_themes`).
**Testing**: pytest (unit com fakes; integração com `httpx.AsyncClient` +
SQLite em memória, como `test_api_admin_dashboard.py`); contrato da port contra
fake e adapter SQLAlchemy.
**Target Platform**: API no container Linux; web SPA.
**Performance Goals**: 90 dias em < 2 s com centenas de conversas. A agregação
é feita em Python sobre as mensagens do período (dezenas de milhares no
máximo hoje); se o volume crescer, a port permite trocar por agregação SQL.
**Constraints**: arquivos de código ≤ 300 linhas efetivas; router sem SQL.
**Scale/Scope**: 6 workspaces, ~85 conversas com workspace hoje.

## Constitution Check

| Princípio | Como o plano cumpre |
|-----------|--------------------|
| I. Spec antes de código | spec, plano e tarefas em `specs/011-…` |
| II. Hexagonal | port `WorkspaceReportRepository`, adapter SQLAlchemy, fake em `tests/fakes_reports.py` registrado no `conftest`, use cases em `use_cases/workspace_report*.py`, router fino |
| III. Gates | ruff, ruff format, mypy, pytest ≥ 80%, lint/build do web |
| IV. Custo e segurança | custo só de `cost_usd`; 403 para admin fora do workspace e para edição de temas sem super admin, com testes negativos |
| V. Evidência | N/A |
| VI. UX | textos em português; estados de carregando, vazio e erro; página segue shadcn/Tailwind do admin atual |

Sem violações.

## Project Structure

### Documentation (this feature)

```text
specs/011-workspace-report-dashboard/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/admin-reports.md
└── tasks.md
```

### Source Code

```text
services/api/
├── alembic/versions/<ts>_add_workspace_report_themes.py
├── app/domain/report_themes.py                 # regras, validação, classificação, modelos prontos
├── app/ports/workspace_report.py               # DTOs + ABC
├── app/adapters/secondary/persistence/sqlalchemy_workspace_report_repo.py
├── app/application/use_cases/workspace_report.py          # escopo, acesso, opções, temas
├── app/application/use_cases/_workspace_report_metrics.py # agregação pura
├── app/adapters/primary/http/admin_reports.py             # rotas
├── app/adapters/primary/http/_admin_reports_export.py     # CSV / XLSX
└── tests/
    ├── fakes_reports.py
    ├── unit/test_report_themes.py
    ├── unit/test_workspace_report_metrics.py
    ├── adapter/test_workspace_report_repo_contract.py
    └── integration/test_api_admin_reports.py
web/src/
├── api/reports.ts (funções e tipos novos, fora do api.ts gigante)
├── pages/AdminReportsPage.tsx
├── pages/AdminReportPrintPage.tsx
└── components/reports/{ReportSections,ReportFilters,ThemeRulesDialog}.tsx
```

**Structure Decision**: segue o padrão hexagonal de `mcp_telemetry`
(port + repo SQLAlchemy + use case + router). Frontend reaproveita
`AdminConsole` e componentes `ui/`.

## Complexity Tracking

Nenhuma.
