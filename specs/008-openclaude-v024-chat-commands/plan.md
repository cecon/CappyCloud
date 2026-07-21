# Implementation Plan: OpenClaude v0.24 Chat Commands

**Branch**: `008-openclaude-v024-chat-commands` | **Date**: 2026-07-20 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/008-openclaude-v024-chat-commands/spec.md`

## Summary

Upgrade the sandbox runtime target from the current OpenClaude v0.17.1 pin to the verified v0.24.0 tag, preserve CappyCloud-owned conversation/model/permission/cost behavior, and expose all upstream slash commands in the chat composer as a discoverable command catalog. Commands without a CappyCloud-safe execution path remain visible but unavailable; commands that alter state, cost, model, context, runtime, branch, session or external access require inline confirmation before execution.

The implementation approach is a coordinated runtime, API, agent and frontend change: rebase and audit local OpenClaude patches against v0.24.0; extend the CappyCloud chat contract for command discovery/execution metadata; keep command authorization in backend use cases and runtime adapters; add a slash-command UX in the existing chat composer without creating a separate terminal surface.

## Technical Context

**Language/Version**: Python/FastAPI backend; TypeScript/React frontend; Node/Bun-built OpenClaude inside the Docker sandbox; protobuf/gRPC for agent runtime streaming.

**Primary Dependencies**: FastAPI, Pydantic, SQLAlchemy, Docker SDK, Redis/PostgreSQL-backed conversation/session behavior, React, existing chat components, OpenRouter/model catalog, OpenClaude gRPC server, sandbox `session_server`.

**Storage**: PostgreSQL for conversations/messages/model access and runtime records; Redis for session cache; Docker volume/worktrees under `/repos`; no new durable storage required unless planning chooses to persist command metadata snapshots.

**Testing**: Backend gates: `ruff check .`, `ruff format --check .`, `mypy app/`, `pytest`. Frontend gates: package install as needed, frontend lint/build under `web/`. Runtime gates: OpenClaude tag verification, sandbox Docker build, focused sandbox/bootstrap tests and manual chat smoke scenarios.

**Target Platform**: Docker Compose development stack, sandbox container running OpenClaude gRPC, authenticated browser chat UI.

**Project Type**: Cross-cutting feature across sandbox runtime, agent bridge, API use cases/contracts and frontend chat UX.

**Performance Goals**: Slash command catalog appears within 2 seconds after typing `/` in 95% of manual smoke attempts; command filtering responds within 150 ms for the discovered command set; no-argument supported commands reach a visible timeline result within 15 seconds when sandbox is already ready.

**Constraints**: CappyCloud remains source of truth for visible history, repository, model, permission mode, token usage and cost. Commands must not bypass repository authorization, model access, permission gates, worktree guards, secret redaction or external-action confirmation. Production rollout, image push and enabling new providers are out of scope.

**Scale/Scope**: One authenticated chat surface, all upstream slash commands discoverable, executable subset gated by CappyCloud-safe mappings. Runtime release scope spans OpenClaude v0.18.0 through v0.24.0 because current sandbox pin is v0.17.1.

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

**Governance note**: This plan does not authorize production deployment, image push or provider enablement. It authorizes local runtime rebuild and validation only.

## Project Structure

### Documentation (this feature)

```text
specs/008-openclaude-v024-chat-commands/
|-- plan.md
|-- research.md
|-- data-model.md
|-- quickstart.md
|-- contracts/
|   |-- api-contract.md
|   |-- runtime-contract.md
|   `-- ui-contract.md
|-- checklists/
|   `-- requirements.md
`-- spec.md
```

### Source Code (repository root)

```text
services/api/
|-- app/
|   |-- application/use_cases/     # command authorization/execution orchestration
|   |-- domain/                    # command value objects if persisted or validated
|   |-- ports/                     # agent/runtime command catalog abstractions
|   |-- adapters/primary/http/     # thin command/catalog endpoints if needed
|   `-- adapters/secondary/        # sandbox/runtime/model catalog adapters
`-- tests/
    |-- unit/
    |-- adapter/
    `-- integration/

services/cappycloud_agent/         # gRPC session and event mapping
services/sandbox/                  # Dockerfile, patches, OpenClaude runtime
proto/                             # gRPC contract if runtime events change
web/                               # React chat composer and timeline UX
```

**Structure Decision**: Keep the existing single API, agent, sandbox and web apps. Add only narrowly scoped command catalog/execution contracts where the existing stream contract cannot express availability, confirmation and command result states.

## Complexity Tracking

No constitution violations are planned.

## Phase 0: Research

See [research.md](research.md).

Key decisions:

- Pin the sandbox to OpenClaude `v0.24.0` tag SHA `2ff93a10bf88ab6d7030fc4ade5316a7424fa2f9`.
- Expose all discovered upstream slash commands in the chat catalog, but execute only commands with CappyCloud-safe mappings.
- Use inline confirmation only for commands that alter state, cost, model, context, runtime, branch, session or external access.
- Prefer a backend-owned command contract over frontend-only parsing so authorization, unavailable reasons and command execution remain testable.
- Treat the exact trigger rule for opening slash suggestions as a UX default: input start or immediately after a newline, unless implementation research finds an accessibility blocker.

## Phase 1: Design

See [data-model.md](data-model.md), [contracts/api-contract.md](contracts/api-contract.md), [contracts/runtime-contract.md](contracts/runtime-contract.md), [contracts/ui-contract.md](contracts/ui-contract.md), and [quickstart.md](quickstart.md).

Design outputs:

- Command catalog and execution state model.
- API contract for command discovery/execution and stream command events.
- Runtime contract for v0.24.0 pinning, patch audit and command-safe execution.
- UI contract for slash suggestions, unavailable states, inline confirmation and timeline results.
- Validation quickstart for release evidence, sandbox build, backend/frontend gates and manual command scenarios.

## Post-Design Constitution Check

- [x] Spec and plan exist; tasks must be generated before implementation.
- [x] Backend command behavior must live in use cases; any new router remains thin.
- [x] Runtime/OpenClaude access must remain behind ports/adapters and sandbox helpers.
- [x] Authorization, model access, repository access, worktree guard, external action and secret redaction requirements are explicit.
- [x] Runtime context remains dynamic: command availability is per conversation/runtime, and model/cost data remain catalog/provider driven.
- [x] Gates are explicit for backend, frontend and sandbox runtime validation.
- [x] Evidence includes repository files, release notes and verified tag SHA.
- [x] Sandbox rebuild is in scope; production deployment and image push are out of scope.

**Constitution risk status**: Passes. The main risk is command overexposure; mitigated by discoverable-but-unavailable states and backend/runtime gates before execution.
