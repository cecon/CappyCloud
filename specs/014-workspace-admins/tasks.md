# Tasks: Admins por workspace

**Input**: [spec.md](spec.md), [plan.md](plan.md)

## Phase 1: Dados e domínio

- [x] T001 Migration `is_admin` em `user_workspace_access` e campo no ORM
- [x] T002 Porta `WorkspaceAdminRepository` e adapter SQLAlchemy
- [x] T003 Use case `admin_scope.py` (escopo, checagem de workspace e de usuário gerenciável) + testes unitários

## Phase 2: API (US1–US4)

- [x] T004 [US1] `get_admin_scope` / `require_workspace_in_scope` em `deps_auth.py`; `admin_workspace_ids` no `/auth/me`
- [x] T005 [US1] Acessos a workspace aceitam escopo; `PUT .../admin` só super admin; GET devolve flag admin
- [x] T006 [US2] Conversas, dashboard, relatórios e CSV de chamados filtrados por escopo
- [x] T007 [US3] Lista de usuários filtrada, reset de senha por admin de workspace, `POST /admin/users/workspace-member`
- [x] T008 [US4] Workspaces (lista, detalhe, PATCH restrito) e conhecimento por escopo
- [x] T009 Testes de integração dos 403 e dos fluxos permitidos

## Phase 3: Frontend

- [x] T010 `admin_workspace_ids` no usuário atual, papel `workspace-admin`, menu e guarda de rota
- [x] T011 Usuários: criar membro, reset, drawer só com workspaces administrados, interruptor "admin" para super admin
- [x] T012 Workspaces: edição restrita; Dashboard/Conversas com lista filtrada

## Phase 4: Entrega

- [ ] T013 Gates (ruff, format, mypy, pytest, vitest, eslint, tsc), PR, deploy, marcar Rodolfo e Aleff como admins do PROTHEUS
