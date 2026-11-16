# Implementation Plan: Times no relatório

**Branch**: `feat/report-teams` | **Spec**: [spec.md](spec.md)

## Technical Context

API FastAPI + SQLAlchemy async + Alembic (Postgres; testes em SQLite). Frontend React/Vite em `web/`. Relatório já existe (spec 011): port `WorkspaceReportRepository`, cálculo puro em `_workspace_report_metrics.py`, rotas em `admin_reports.py`.

## Constitution Check

- Arquitetura hexagonal: regra de time no cálculo puro e nos use cases; SQL só no adapter. OK.
- Segurança: permissões usam `AdminScope` (`ensure_workspace`, `ensure_can_grant`) no backend, não só na UI. OK.
- Custo: nada muda na origem do custo (`messages.cost_usd`). OK.
- Layout: revisão no Docker local antes de subir. OK.

## Design

### Dados

- Tabela `workspace_teams(id uuid pk, workspace_id fk workspaces on delete cascade, name varchar(128), created_at)`, índice único `(workspace_id, lower(name))`.
- `user_workspace_access.team_id uuid null fk workspace_teams on delete set null`.

### API

- `GET/POST /admin/workspaces/{workspace_id}/teams`, `PATCH/DELETE /admin/workspaces/{workspace_id}/teams/{team_id}`: escopo `get_admin_scope` + `scope.ensure_workspace`.
- `GET /admin/users/{user_id}/access/workspaces/teams` → `{workspace_id: team_id}` dos workspaces visíveis.
- `PUT /admin/users/{user_id}/access/workspaces/{workspace_id}/team` `{team_id: uuid|null}`: `ensure_can_grant`, cria o acesso se faltar, valida que o time é do workspace.
- Relatório: parâmetro `team` em report/export; `teams` nas opções; `teams` (quadro) no relatório; `team` em analistas e conversas.

### Cálculo

- `ReportConversation.team: str | None` vem do acesso (user, workspace da conversa).
- Filtro por time igual ao de branch; `"__none__"` = sem time.
- `TeamRow(name, analysts, questions, conversations, cost_usd, share)`; "Sem time" por último.

### Frontend

- Workspaces: seção "Times" (lista, adicionar, renomear, apagar).
- Usuários → Acessos → Workspaces: seletor de time por workspace liberado.
- Relatórios: filtro Time, quadro "Por time", coluna Time em analistas e conversas.
