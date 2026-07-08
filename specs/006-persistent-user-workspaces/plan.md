# Implementation Plan: Persistent User Workspaces

**Branch**: `[006-persistent-user-workspaces]` | **Date**: 2026-07-08 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/006-persistent-user-workspaces/spec.md`

## Summary

Persist a prepared repository workspace per user, repository, and base branch inside the shared sandbox so repeated conversations can reuse a clean baseline. Mutating flows continue to run in isolated conversation/task workspaces derived from that user baseline, preserving cross-user and cross-conversation isolation while reducing repeated setup cost.

## Technical Context

**Language/Version**: Python 3.14/FastAPI backend, TypeScript/React frontend, Node.js sandbox sidecar, shell-based Git helpers.

**Primary Dependencies**: FastAPI, SQLAlchemy/Alembic, asyncpg, Redis session cache, Docker Compose sandbox, OpenClaude gRPC, React/Mantine.

**Storage**: PostgreSQL for user workspace registry and lifecycle state; Redis for hot agent session cache; persistent `/repos` Docker volume for repository clones, user workspaces, and conversation/task worktrees.

**Testing**: Backend `ruff check`, `ruff format --check`, `mypy app/`, `pytest`; frontend lint/build if UI status changes; Docker Compose smoke test for sandbox/session server behavior.

**Target Platform**: Local and deployed Docker Compose/Swarm-style CappyCloud stack with shared sandbox containers and browser UI.

**Project Type**: Backend API, agent runtime, sandbox sidecar, and optional frontend status copy.

**Performance Goals**: Repeat conversations for the same user/repository/base branch should avoid full workspace creation in at least 95% of normal cases and should visibly prepare at least 70% faster than the first preparation.

**Constraints**: No cross-user filesystem leakage; no reuse of dirty mutable task workspaces as clean baselines; no hardcoded repository catalog; no automatic push or external write action introduced by baseline reuse.

**Scale/Scope**: First release targets one shared sandbox pool and the existing repository catalog. It supports multi-user reuse, concurrent preparation, workspace repair, and cleanup of stale baselines.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] Non-trivial change has a spec, plan, and task breakdown, or the direct bugfix/operational exception is justified.
- [x] Backend business rules are in `services/api/app/application/use_cases/`; HTTP routers stay thin and contain no SQL or domain decisions.
- [x] External systems are behind ports/adapters, with fakes and contract tests when behavior is shared.
- [x] Security, authorization, repository visibility, and cross-user access implications are explicit.
- [x] Runtime context is dynamic: selected repos, skills, MCPs, docs, model, and cost are not hardcoded.
- [x] Required gates are planned: `ruff check`, `ruff format --check`, `mypy app/`, `pytest`, and frontend lint/build when `web/` changes.
- [x] Evidence requirements are clear for code, external docs, URLs, and line references when available.
- [x] Sandbox/worktree/Git behavior is explicit, especially branch creation, automatic push, container rebuilds, and network calls.

## Project Structure

### Documentation (this feature)

```text
specs/006-persistent-user-workspaces/
|-- plan.md
|-- research.md
|-- data-model.md
|-- quickstart.md
|-- contracts/
|   |-- user-workspaces-api.md
|   `-- sandbox-session-server.md
`-- tasks.md
```

### Source Code (repository root)

```text
services/api/
|-- app/
|   |-- domain/entities.py
|   |-- application/use_cases/
|   |-- ports/
|   |-- adapters/primary/http/
|   |-- adapters/secondary/persistence/
|   |-- infrastructure/orm_models*.py
|   `-- schemas*.py
|-- alembic/versions/
`-- tests/
    |-- unit/
    |-- adapter/
    `-- integration/

services/cappycloud_agent/
|-- _environment_manager.py
|-- _session_store.py
|-- _task_launcher.py
`-- _worktree_validation.py

services/sandbox/
|-- session_server.js
|-- session_start.sh
|-- worktree_handlers.js
`-- repo_handlers.js

web/
`-- src/pages/ChatPage.tsx
```

**Structure Decision**: Reuse the existing API hexagonal layout for workspace registry and authorization, the existing agent `EnvironmentManager` for runtime orchestration, and the sandbox `session_server` for all filesystem/Git operations. UI changes are limited to status/copy if the backend exposes distinct reuse/repair states.

## Phase 0: Research

Research completed in [research.md](research.md).

## Phase 1: Design & Contracts

- Data model: [data-model.md](data-model.md)
- API contract: [contracts/user-workspaces-api.md](contracts/user-workspaces-api.md)
- Sandbox contract: [contracts/sandbox-session-server.md](contracts/sandbox-session-server.md)
- Validation guide: [quickstart.md](quickstart.md)

## Post-Design Constitution Check

- [x] Business logic remains planned for use cases; routers remain thin.
- [x] Workspace persistence uses ports/adapters and contract tests where shared.
- [x] Authorization and cross-user isolation are explicit in data model and contracts.
- [x] Runtime context remains driven by user/conversation/repository selection.
- [x] Sandbox and Git behavior is explicit, with no automatic push introduced.
- [x] Required gates and Docker smoke checks are documented in quickstart.

## Complexity Tracking

No constitution violations requiring waiver.
