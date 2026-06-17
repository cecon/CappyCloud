# Implementation Plan: Agentic Delivery Factory

**Branch**: `001-agentic-delivery-factory` (feature directory; no git branch active) | **Date**: 2026-06-16 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/001-agentic-delivery-factory/spec.md`

## Summary

Implement an agentic delivery cycle workflow inside CappyCloud so authorized users can prepare structured work packages, allow agents to generate review-only changes in sandbox/worktrees, review outputs through mandatory gates, preserve reusable knowledge with repository/domain isolation, and track cycle value metrics. The technical approach follows the existing hexagonal API: domain entities and lifecycle rules in `services/api/app/domain/`, orchestration in `services/api/app/application/use_cases/`, persistence and retrieval behind ports/adapters, thin FastAPI routers, agent runtime context extensions, and React/Mantine UI screens for cycle creation and review.

## Technical Context

**Language/Version**: Python/FastAPI backend, TypeScript/React frontend, Node sandbox sidecar, CappyCloud Python agent runtime.

**Primary Dependencies**: FastAPI, Pydantic, SQLAlchemy async, Alembic, PostgreSQL with pgvector, Redis/session cache, React, Mantine, Docker sandbox, OpenRouter usage/cost reporting.

**Storage**: PostgreSQL for cycles, work packages, outputs, gates, agentic delivery permissions, authorizations, knowledge items, sensitive surfaces, and metrics; existing sandbox/worktree filesystem for generated changes; existing message/cost tables for model usage correlation.

**Testing**: `ruff check .`, `ruff format --check .`, `mypy app/`, `pytest` for API; frontend lint/build for `web/`; focused unit/integration/adapter tests for authorization, lifecycle, retrieval isolation, gate triggering, and contracts.

**Target Platform**: Existing Docker Compose CappyCloud stack: FastAPI API, PostgreSQL, Redis, sandbox container, browser UI.

**Project Type**: Cross-cutting product feature touching API, persistence, agent runtime context, sandbox/worktree behavior, and frontend.

**Performance Goals**: Work package creation completes in under 5 seconds for a single-repository cycle; review package loads in under 3 seconds for moderate cycles; knowledge retrieval returns relevant authorized items in under 2 seconds; metrics summary loads in under 3 seconds.

**Constraints**: No automatic push, deployment, or irreversible external action; repository/domain access must be enforced in retrieval before content reaches the agent; sensitive surface management and action authorization must use explicit `AgenticDeliveryPermission` grants rather than ordinary repository visibility alone; prompt guidance is not an access control; compliance gate triggering must be deterministic from configured sensitive surfaces.

**Scale/Scope**: MVP supports single-repository and small multi-repository cycles, up to 100 evidence sources, 50 agent outputs, 20 review decisions, and 1,000 reusable knowledge items per repository/domain without changing the user workflow.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

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
specs/001-agentic-delivery-factory/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── http-api.md
└── tasks.md
```

### Source Code (repository root)

```text
services/api/
├── alembic/versions/                         # schema migration for cycle tables
├── app/
│   ├── domain/agentic_delivery.py            # cycle value objects and enums
│   ├── application/use_cases/
│   │   ├── agentic_delivery_prepare.py       # create/prepare/run cycle orchestration
│   │   ├── agentic_delivery_review.py        # review decisions, gates, transitions
│   │   ├── agentic_delivery_knowledge.py     # isolated knowledge retrieval/reuse
│   │   ├── agentic_delivery_actions.py       # external action authorization
│   │   └── agentic_delivery_metrics.py       # cycle metrics
│   ├── ports/
│   │   ├── agentic_delivery.py               # persistence/retrieval/permission/action ports
│   │   └── user_access.py                    # permission checks reused/extended
│   ├── adapters/primary/http/
│   │   ├── agentic_delivery.py               # thin HTTP adapter
│   │   └── deps.py                           # use case composition
│   ├── adapters/secondary/persistence/
│   │   └── sqlalchemy_agentic_delivery_repo.py
│   ├── infrastructure/
│   │   └── orm_models_agentic_delivery.py
│   └── schemas_agentic_delivery.py
└── tests/
    ├── unit/use_cases/test_agentic_delivery.py
    ├── adapter/test_sqlalchemy_agentic_delivery_repo.py
    └── integration/test_api_agentic_delivery.py

services/cappycloud_agent/
├── _agent_context.py                         # include cycle context for agent runs
├── _agent_prompt_sections.py                 # render work package/review constraints
└── cappycloud_pipeline.py                    # propagate cycle metadata

web/src/
├── api.ts                                    # client contracts
├── components/agentic-delivery/              # cycle creation/review components
├── pages/AgenticDeliveryPage.tsx
└── App.tsx                                   # route registration

docs/
└── how-to/agentic-delivery-factory.md
```

**Structure Decision**: Use the existing API hexagonal boundaries and add a dedicated feature slice. The database schema and SQLAlchemy adapter are isolated under persistence, existing `UserRepositoryAccess` remains the visibility check, `AgenticDeliveryPermission` grants privileged feature actions, use cases own lifecycle/gate/security decisions, HTTP stays thin, agent runtime receives only already-authorized cycle context, and the frontend consumes typed API contracts from `web/src/api.ts`. Use cases are split by responsibility so implementation can stay below the repository 300 effective line limit per file.

## Phase 0: Research

Completed in [research.md](research.md).

## Phase 1: Design & Contracts

Completed in [data-model.md](data-model.md), [contracts/http-api.md](contracts/http-api.md), and [quickstart.md](quickstart.md).

## Post-Design Constitution Check

- [x] Domain rules are modeled as use cases and value objects, not router logic.
- [x] Persistence, knowledge retrieval, external action execution, and agent context propagation are behind explicit ports/adapters.
- [x] Repository/domain isolation, gate completion, lifecycle transitions, compliance triggering, and external action authorization are server-side controls.
- [x] Runtime context remains dynamic and tied to conversation, repository, sandbox, skills, MCPs, selected model, provider usage, and cost data.
- [x] Tests and validation gates are planned for backend, frontend, and security-critical behavior.

## Complexity Tracking

No constitution violations require justification.
