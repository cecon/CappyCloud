# Implementation Plan: Admins por workspace

**Branch**: `feat/workspace-admins` | **Date**: 2026-10-21 | **Spec**: [spec.md](spec.md)

## Summary

Um usuário vira admin de um workspace por uma coluna `is_admin` no acesso `user_workspace_access`. Uma dependência nova, `get_admin_scope`, resolve quem chama as rotas administrativas: ADMIN global (sem limite) ou admin de workspace (lista de ids). As rotas de conversas, dashboard, relatórios, chamados, usuários, acessos a workspace, workspaces e conhecimento passam a aceitar esse escopo e a filtrar/negar por workspace. O frontend recebe `admin_workspace_ids` no `/auth/me` e mostra as telas permitidas.

## Technical Context

**Language/Version**: Python 3.12 / FastAPI; TypeScript / React
**Primary Dependencies**: FastAPI, SQLAlchemy async, Alembic; React, Tailwind/shadcn (legacy wrappers)
**Storage**: PostgreSQL — coluna nova `user_workspace_access.is_admin`
**Testing**: ruff, ruff format, mypy, pytest (unit com fakes + adapter com SQLite), vitest, eslint, tsc
**Target Platform**: stack Dokploy (api + web)
**Project Type**: API + frontend
**Constraints**: nenhuma rota pode vazar dado de outro workspace para admin de workspace
**Scale/Scope**: ~60 usuários, 6 workspaces

## Constitution Check

- **I. Spec antes do código**: esta spec/plano/tarefas.
- **II. Hexagonal**: a decisão de escopo fica em `application/use_cases/admin_scope.py` sobre a porta `ports/workspace_admin.py`; o adapter SQLAlchemy implementa a porta. Os routers de workspace e conversas já usam ORM direto (código existente); só acrescentam o filtro vindo do escopo.
- **III. Gates**: ruff, format, mypy, pytest, vitest, eslint, tsc.
- **IV. Segurança**: escopo checado na API; testes de 403 para outro workspace, para alvo ADMIN e para promoção por não super admin.
- **VI. UX**: erros 403 com mensagem em português; a UI esconde o que não pode.

## Design

### Dados
- Migration `add_workspace_admin_flag`: `user_workspace_access.is_admin BOOLEAN NOT NULL DEFAULT false`.

### Backend
- `ports/workspace_admin.py` (`WorkspaceAdminRepository`): `admin_workspace_ids(user_id)`, `member_workspace_ids(user_id)`, `is_any_workspace_admin(user_id)`.
- `application/use_cases/admin_scope.py`:
  - `AdminScope(user, workspace_ids: frozenset | None)`; `None` = global. Métodos `is_global`, `allows(workspace_id)`, `filter_ids`.
  - `ResolveAdminScope.execute(user)` → escopo ou `AdminScopeDeniedError`.
  - `ensure_workspace(scope, ws_id)`; `ensure_manageable_user(scope, target, repo)` (USER, não admin de workspace, não ele mesmo, com acesso a workspace do escopo).
- `deps_auth.get_admin_scope` (403 se não for nenhum dos dois) e `require_workspace_in_scope` (para rotas com `{workspace_id}` no path).
- Rotas:
  - `admin_conversations`: escopo; lista filtra `workspace_id IN scope`; detalhe nega fora do escopo.
  - `admin_dashboard`: escopo; `workspace_id` precisa estar no escopo; sem ele, agrega os workspaces do escopo.
  - `admin_reports`: `ReportViewer` ganha `admin_workspace_ids`; `visible_workspaces` usa essa lista quando definida.
  - `workspace_tickets`: `require_workspace_in_scope`.
  - `admin_users`: lista filtrada; `reset-password` aceita super admin ou admin de workspace com alvo gerenciável; `POST /admin/users/workspace-member` cria/associa USER.
  - `admin_workspaces`: lista/detalhe filtrados; PATCH de admin de workspace só aceita `claude_md`, `require_ticket`, `plan_mode_enabled`; criar/excluir/sync seguem super admin. Rotas de acesso aceitam escopo; `PUT .../{workspace_id}/admin` só super admin; GET devolve também quais acessos são admin.
  - `admin_workspace_knowledge`: `require_workspace_in_scope`.
  - `auth/me`: `admin_workspace_ids`.

### Frontend
- `CurrentUser.admin_workspace_ids`; `roleFromUser` → `'workspace-admin'`.
- `navigation.ts`: flag `workspaceAdmin` em Dashboard, Conversas, Relatórios, Usuários, Workspaces.
- `RequireAdmin` aceita admin de workspace; rota `/admin/workspaces` passa a `AdminPage`.
- Usuários: botão "Novo usuário" abre modal com seletor de workspace (admin de workspace); menu sem papel; reset de senha visível; drawer só com aba Workspaces e só os workspaces administrados; super admin vê o interruptor "admin" por workspace.
- Workspaces: admin de workspace não vê criar/excluir/sync nem editor de repositórios.
- Dashboard/Conversas: lista de workspaces filtrada por `admin_workspace_ids`.

## Project Structure

```
services/api/alembic/versions/20261021_160000_add_workspace_admin_flag.py
services/api/app/ports/workspace_admin.py
services/api/app/application/use_cases/admin_scope.py
services/api/app/adapters/secondary/persistence/sqlalchemy_workspace_admin_repo.py
services/api/app/adapters/primary/http/{deps_auth,admin_conversations,admin_dashboard,admin_reports,workspace_tickets,admin_users,admin_workspaces,admin_workspace_knowledge,auth}.py
services/api/tests/unit/use_cases/test_admin_scope.py
services/api/tests/integration/test_api_workspace_admins.py
web/src/{api/auth.ts,api/workspaces*.ts,components/layout/navigation.ts,components/RequireAdmin.tsx,App.tsx,pages/AdminUsersPage.tsx,pages/admin-users/*,components/UserAccessDrawer.tsx,pages/AdminWorkspacesPage.tsx,pages/AdminDashboardPage.tsx,pages/AdminConversationsPage.tsx}
```

## Complexity Tracking

Nenhuma violação.
