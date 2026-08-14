# Implementation Plan: OpenClaude Current Upgrade UI Readiness

**Branch**: `008-openclaude-current-upgrade` | **Date**: 2026-08-06 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/008-openclaude-current-upgrade/spec.md`

## Summary

Upgrade the CappyCloud sandbox runtime target from the production-observed
OpenClaude 0.24.0 baseline to the frozen OpenClaude 0.27.0 target, while
adapting or validating the CappyCloud UI surfaces affected by OpenClaude 0.25.0,
0.26.0 and 0.27.0. The plan preserves CappyCloud as the source of truth for
visible chat state, model authorization, provider availability, usage and cost.
It adds a discrete execution-time context indicator, grouped/collapsible
subagent activity, administrator-only provider auth/onboarding states, local
validation, and a rollout/rollback runbook. Production deployment is explicitly
out of scope.

## Technical Context

**Language/Version**: Python/FastAPI backend, TypeScript/React frontend, Node
sandbox sidecars, Docker sandbox runtime. Frontend package metadata records
React 19, Vite, Tailwind 4 and Radix/shadcn-compatible dependencies.

**Primary Dependencies**: FastAPI, SQLAlchemy, React, Tailwind/Radix UI
components, Docker sandbox, Bun-built OpenClaude source, OpenRouter/provider
catalog, gRPC/protobuf, Redis session coordination.

**Storage**: PostgreSQL for conversations/messages/model catalog/provider
state, Redis for runtime/session coordination, Docker image layers for
OpenClaude, and filesystem/worktrees under sandbox volumes.

**Testing**: `ruff check`, `ruff format --check`, `mypy app/`, `pytest`,
frontend lint/build (`pnpm --dir web lint`, `pnpm --dir web build`), sandbox
image build with OpenClaude 0.27.0, and manual quickstart validation scenarios.

**Target Platform**: Local Docker Compose stack and browser UI for validation.
Production Swarm/Portainer rollout is excluded from this feature.

**Project Type**: Cross-cutting sandbox runtime, agent bridge, API contract,
frontend UI, admin UI, and documentation/runbook change.

**Performance Goals**: Long-running tool turns remain visibly active without
premature stale-state errors; users can identify active work, timeout,
cancellation or final failure in under 10 seconds; the discrete context
indicator does not block streaming or final response rendering.

**Constraints**: CappyCloud remains authoritative for visible history,
permission mode, selected repositories, selected model, provider availability,
usage and cost. Live context/token information is progress-only and not
financial. Provider onboarding/OAuth state is administrator-only. Subagent
activity is grouped and collapsible inside the parent turn. OpenClaude 0.27.0
is frozen for this feature.

**Scale/Scope**: One OpenClaude target update plus validation/adaptation of
chat activity states, context indicator, subagent grouping, provider/admin
states, model picker/catalog behavior, local sandbox build, and a
rollout/rollback runbook.

## Constitution Check

*GATE: Passed before Phase 0 research. Re-check after Phase 1 design: passed.*

- [x] Non-trivial change has a spec, plan, and task breakdown, or the direct
      bugfix/operational exception is justified.
- [x] Backend business rules are in `services/api/app/application/use_cases/`;
      HTTP routers stay thin and contain no SQL or domain decisions.
- [x] External systems are behind ports/adapters, with fakes and contract tests
      when behavior is shared.
- [x] Security, authorization, repository visibility, and cross-user access
      implications are explicit.
- [x] Runtime context is dynamic: selected repos, skills, MCPs, docs, model, and
      cost are not hardcoded.
- [x] Required gates are planned: `ruff check`, `ruff format --check`,
      `mypy app/`, `pytest`, and frontend lint/build when `web/` changes.
- [x] Evidence requirements are clear for code, external docs, URLs, and line
      references when available.
- [x] Sandbox/worktree/Git behavior is explicit, especially branch creation,
      automatic push, container rebuilds, and network calls.

## Project Structure

### Documentation (this feature)

```text
specs/008-openclaude-current-upgrade/
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
|-- env_init.sh
|-- entrypoint.sh
|-- session_server.js
`-- session_start.sh

services/cappycloud_agent/
|-- _grpc_session.py
|-- _grpc_event_handlers.py
|-- _grpc_bridge.py
|-- _session_store.py
`-- cappycloud_pipeline.py

services/api/
|-- app/application/use_cases/
|-- app/adapters/primary/http/
|-- app/adapters/secondary/
|-- app/ports/
|-- app/schemas*.py
`-- tests/

proto/
`-- openclaude.proto

web/
|-- src/api.ts
|-- src/pages/
|-- src/components/
|-- src/components/admin/
|-- src/components/chat/
`-- src/components/ui/

docs/
|-- ARCHITECTURE.md
|-- AGENT_RULES.md
`-- how-to/agent-runtime-context.md
```

**Structure Decision**: Use existing runtime/API/frontend boundaries. The
sandbox owns the OpenClaude pin and local patch compatibility; the agent bridge
normalizes gRPC/runtime events; API use cases preserve authorization, model
catalog and persisted usage/cost behavior; the frontend owns the discrete
context indicator, grouped subagent activity and admin-only provider auth
states; documentation owns local validation and rollout/rollback guidance.

## Complexity Tracking

No constitution violations are planned.
