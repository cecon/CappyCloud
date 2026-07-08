# Implementation Plan: OpenClaude v0.15.0 Permission Mode Upgrade

**Branch**: `[003-openclaude-v015-ui-audit]` | **Date**: 2026-06-17 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/003-openclaude-v015-ui-audit/spec.md`

## Summary

Update the sandbox runtime target to OpenClaude v0.15.0, audit local OpenClaude
patches against tag `670744fc70353f2270e86531dffa1c06f4fac79c`, and add a
chat-level session permission mode selector. New conversations default to
`solicitar permissoes`; the selected mode is stored with the conversation,
sent on every agent execution, and mapped into the headless OpenClaude gRPC
runtime. Warning severity comes from the selected mode only: high-risk for
`modo automatico` and `ignorar permissoes`, lower-severity caution for
`aceitar edicoes`, and no provider classification. Legacy process-wide
auto-approval parameters must be removed or neutralized so they do not override
the per-session mode.

## Technical Context

**Language/Version**: Python/FastAPI backend, TypeScript/React frontend, Node.js sandbox/OpenClaude runtime, protobuf/gRPC for agent stream.

**Primary Dependencies**: FastAPI, Pydantic, SQLAlchemy async, Alembic, PostgreSQL JSONB, React, Vite, Mantine, Docker sandbox image, OpenClaude upstream, gRPC/protobuf.

**Storage**: PostgreSQL for conversation permission mode; existing Redis/session storage for agent sessions; Docker/worktree filesystem unchanged.

**Testing**: Backend `ruff check`, `ruff format --check`, `mypy app/`, `pytest` including agent-runtime regression tests loaded from `services/api/tests/unit/`; frontend lint/build when `web/` changes; sandbox image build and manual runtime validation for OpenClaude patches.

**Target Platform**: Browser chat UI, FastAPI API, CappyCloud agent pipeline, Docker sandbox container running OpenClaude headless.

**Project Type**: Cross-cutting API + frontend + agent runtime + sandbox version update.

**Performance Goals**: Permission mode selection must not add an extra network round trip before sending a chat message; stream startup remains bounded by existing session bootstrap/runtime latency.

**Constraints**: New sessions default to `solicitar permissoes`; warning severity is mode-derived, not provider-derived; legacy process-wide auto-approval defaults cannot remain active; no raw provider secrets, hidden prompts, repository contents, tool inputs, or raw container logs may be exposed.

**Scale/Scope**: One chat-level selector and API/runtime propagation for all conversations; one OpenClaude version bump and local patch audit; no production rollout or Portainer/Swarm deployment.

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
specs/003-openclaude-v015-ui-audit/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── session-permission-mode.md
│   └── openclaude-runtime.md
└── tasks.md             # Created later by /speckit-tasks
```

### Source Code (repository root)

```text
services/api/
├── alembic/versions/                 # add conversation permission mode migration
├── app/
│   ├── domain/entities.py            # Conversation permission_mode field
│   ├── schemas_conversations.py      # HTTP request/response contract
│   ├── application/use_cases/
│   │   ├── conversations.py          # stream use case orchestration
│   │   └── _stream_helpers.py        # pipeline body construction
│   ├── ports/repositories.py         # ConversationRepository contract if needed
│   ├── adapters/primary/http/
│   │   └── conversations.py          # thin request glue only
│   └── adapters/secondary/
│       └── persistence/              # SQLAlchemy conversation mapping
└── tests/
    ├── unit/use_cases/
    ├── unit/test_agent_permission_mode.py
    ├── integration/
    └── adapter/

services/cappycloud_agent/
├── cappycloud_pipeline.py            # consume permission_mode from pipeline body
└── _grpc_session.py                  # send permission_mode in ChatRequest

services/sandbox/
├── Dockerfile                        # OPENCLAUDE_REF v0.15.0
├── env_init.sh                       # remove legacy process-wide mode defaults
└── patches/                          # local OpenClaude patch audit/update

proto/
└── openclaude.proto                  # add permission_mode field to ChatRequest

web/
└── src/
    ├── api.ts                        # typed permission mode API contract
    └── pages/ChatPage.tsx            # selector, warning, stream payload
```

**Structure Decision**: Use the existing conversation stream boundary and agent
pipeline body rather than adding a separate per-session settings service. The
HTTP router remains thin; the use case validates/applies the mode and the
pipeline/runtime receives the already-resolved session context.

## Phase 0: Research

See [research.md](research.md).

Key decisions:

- Persist the current permission mode on the `Conversation` record.
- Send the selected mode in `SendMessageBody` for each new execution.
- Add `permission_mode` to `ChatRequest` so OpenClaude headless mode can apply
  behavior per request instead of relying on global `OPENCLAUDE_AUTO_APPROVE`.
- Surface sanitized OpenClaude startup warning context through existing
  `status` metadata when safely detected.
- Remove or neutralize legacy global auto-approval parameters from sandbox
  startup and patch generation paths.
- Keep provider classification out of warning severity.
- Keep CappyCloud hard safety boundaries even when the user selects the most
  permissive mode.

## Phase 1: Design

See [data-model.md](data-model.md), [contracts/session-permission-mode.md](contracts/session-permission-mode.md),
[contracts/openclaude-runtime.md](contracts/openclaude-runtime.md), and [quickstart.md](quickstart.md).

### Post-Design Constitution Check

- [x] Backend persistence and permission-mode selection stay in use cases and
      repositories; routers only pass validated request fields.
- [x] Runtime changes preserve ports/adapters: API talks to `AgentPort`, the
      concrete pipeline adapter remains isolated, and gRPC changes stay behind
      the agent/sandbox boundary.
- [x] Security behavior is explicit: warnings derive from mode, not provider
      classification; sanitized runtime confirmation may enrich the warning;
      secrets and raw logs remain hidden.
- [x] Dynamic runtime context remains intact: model selection, repositories,
      skills, MCPs, attachments, cost, and provider config are still request- or
      conversation-derived.
- [x] Required gates and manual sandbox validation are recorded in quickstart.
- [x] Sandbox build and OpenClaude patch audit are explicit; deployment is out
      of scope.

## Complexity Tracking

No constitution violations identified. No complexity exception is required.
