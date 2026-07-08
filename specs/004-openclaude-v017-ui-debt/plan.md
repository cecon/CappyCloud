# Implementation Plan: OpenClaude v0.17.1 UI Debt Audit

**Branch**: `004-openclaude-v017-ui-debt` | **Date**: 2026-07-08 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/004-openclaude-v017-ui-debt/spec.md`

## Summary

Update the sandbox OpenClaude runtime target from the current v0.15.0 pin to
the v0.17.1 tag SHA, then validate the CappyCloud-owned chat, model catalog,
permission, usage/cost, search, diagnostics, and admin surfaces that can be
affected by v0.16.0 through v0.17.1. The implementation keeps CappyCloud as the
source of truth for visible conversation state and authorized model/catalog
behavior, while constraining OpenClaude cache/session/fallback features to
runtime-internal behavior unless CappyCloud can surface sanitized metadata.

## Technical Context

**Language/Version**: Python/FastAPI backend, TypeScript/React frontend, Node
sandbox sidecars, Docker sandbox runtime.

**Primary Dependencies**: FastAPI, SQLAlchemy, React, Mantine, Vite, Docker,
OpenRouter, gRPC/protobuf, OpenClaude source built from
`https://github.com/Gitlawb/openclaude.git`.

**Storage**: PostgreSQL for conversations/messages/catalog/runtime metadata,
Redis for agent session TTL, filesystem/worktrees under `/repos/sessions`, and
Docker image layers for the pinned OpenClaude build.

**Testing**: `ruff check`, `ruff format --check`, `mypy app/`, `pytest`,
frontend lint/build for `web/`, sandbox image build with the pinned
`OPENCLAUDE_REF`, and manual validation scenarios in `quickstart.md`.

**Target Platform**: Docker Compose stack with sandbox containers, browser UI,
and the FastAPI API that streams chat events to the React client.

**Project Type**: Cross-cutting runtime, API, frontend, sandbox, and docs
change.

**Performance Goals**: No duplicated or stale visible conversation state during
session resume/switch; no additional blocking UI wait beyond existing stream
startup behavior; preserve usable multi-session behavior after the runtime
upgrade.

**Constraints**: CappyCloud remains authoritative for visible history,
permission mode, selected repositories, selected model, usage, and cost.
Automatic fallback is allowed only to authorized models. Secrets, hidden
prompts, raw logs, repository content, and unsanitized tool inputs must not
appear in UI warnings, diagnostics, or errors.

**Scale/Scope**: One sandbox runtime pin plus validation of the chat page,
model picker/catalog/admin states, conversation search, payload diagnostics,
tool/action events, and sandbox patches.

## Constitution Check

*GATE: Passed before Phase 0 research. Re-check after Phase 1 design: passed.*

- [x] Non-trivial runtime/frontend/API change has a spec, this plan, and will
      have a task breakdown before implementation.
- [x] Backend business rules stay in `services/api/app/application/use_cases/`;
      HTTP routers remain request/response adapters only.
- [x] External systems stay behind existing ports/adapters. New shared runtime
      behavior must add fakes/contract tests if it changes use-case contracts.
- [x] Security, authorization, repository visibility, model authorization, and
      cross-user implications are explicit in the spec and validation contract.
- [x] Runtime context stays dynamic: repository, skills, MCPs, documentation,
      selected model, provider usage, and cost are not hardcoded.
- [x] Required gates are planned: `ruff check`, `ruff format --check`,
      `mypy app/`, `pytest`, frontend lint/build, and sandbox image build.
- [x] Evidence requirements are clear: code references in repo docs and
      OpenClaude release/tag evidence already captured by the spec.
- [x] Sandbox/worktree/Git behavior is explicit: update Docker build pin and
      patches only; no production rollout, image push, branch push, or automatic
      container replacement in this feature.

## Project Structure

### Documentation (this feature)

```text
specs/004-openclaude-v017-ui-debt/
|-- plan.md
|-- research.md
|-- data-model.md
|-- quickstart.md
|-- contracts/
|   `-- runtime-ui-contract.md
|-- checklists/
|   `-- requirements.md
`-- tasks.md
```

### Source Code (repository root)

```text
services/sandbox/
|-- Dockerfile
|-- patches/
|-- session_server.js
`-- session_start.sh

services/cappycloud_agent/
|-- cappycloud_pipeline.py
|-- _grpc_session.py
|-- _grpc_event_handlers.py
`-- _session_store.py

services/api/
|-- app/application/use_cases/
|-- app/adapters/primary/http/conversations.py
|-- app/ports/
|-- app/infrastructure/orm_models*.py
`-- tests/

proto/
`-- openclaude.proto

web/
|-- src/api.ts
|-- src/pages/ChatPage.tsx
|-- src/pages/AdminModelsPage.tsx
|-- src/pages/AdminProvidersPage.tsx
`-- src/components/

docs/
|-- ARCHITECTURE.md
`-- how-to/agent-runtime-context.md
```

**Structure Decision**: Use the existing runtime/API/frontend boundaries. The
sandbox owns the OpenClaude pin and local patches; `services/cappycloud_agent`
owns gRPC event normalization and runtime session behavior; API use cases own
conversation/catalog authorization and cost persistence; React/Mantine screens
own visible state and validation of chat/model/search/admin surfaces.

## Complexity Tracking

No constitution violations are planned.
