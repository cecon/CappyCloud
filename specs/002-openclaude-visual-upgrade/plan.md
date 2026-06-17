# Implementation Plan: OpenClaude v0.14.0 Chat Visual Upgrade

**Branch**: `(not created by Spec Kit hook)` | **Date**: 2026-06-17 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/002-openclaude-visual-upgrade/spec.md`

## Summary

Update the sandbox OpenClaude runtime to v0.14.0, audit the existing local
OpenClaude patches against that upstream version, and surface the new request
payload size diagnostics in CappyCloud chat as structured, sanitized turn
metadata. Diagnostics will be persisted with the assistant message so reloads
show the same compact summary: total payload size plus the three largest safe
categories, with all safe categories available in an expanded view. Existing
visual treatments for timeouts, tool errors, action prompts, resume, and usage
remain the baseline and must be regression-tested.

## Technical Context

**Language/Version**: Python >=3.14 API, TypeScript 6.0 + React 19.2 + Mantine 9 frontend, Node 20 sandbox runtime.

**Primary Dependencies**: FastAPI, Pydantic, SQLAlchemy async, Alembic, PostgreSQL JSONB, gRPC/protobuf, Docker sandbox image, OpenClaude upstream, React/Vite/Mantine.

**Storage**: PostgreSQL for messages, agent tasks, and agent events. Add safe payload diagnostic JSONB to persisted chat messages. Redis/session/worktree storage is unchanged.

**Testing**: `ruff check`, `ruff format --check`, `mypy app/`, `pytest`, plus `pnpm --dir web lint` and `pnpm --dir web build` because `web/` changes are expected. Add focused unit, adapter, integration, and frontend checks for diagnostic persistence/rendering.

**Target Platform**: Docker Compose API + sandbox containers, browser chat UI. Production image rebuild/deploy is outside this plan unless explicitly requested later.

**Project Type**: API, agent runtime bridge, sandbox runtime, frontend chat UI, and documentation/design artifacts.

**Performance Goals**: Diagnostic processing must not add an extra network round trip to a chat turn. Reloaded conversation history should include persisted diagnostics in the normal messages response. Users must identify the largest payload category in under 10 seconds.

**Constraints**: Do not expose secrets, raw provider keys, hidden prompts, full tool inputs, raw files, or binary attachment data. Keep backend business logic in use cases, keep routers thin, update fakes and adapter contract tests when the message contract changes, and keep implementation files under the repository line limit.

**Scale/Scope**: One optional payload diagnostic object per assistant turn. Category lists are expected to be small and bounded by known safe categories, not by files, tools, or raw prompt fragments.

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
specs/002-openclaude-visual-upgrade/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── chat-diagnostics.md
└── tasks.md             # Created later by /speckit-tasks
```

### Source Code (repository root)

```text
proto/
└── openclaude.proto                     # internal agent stream contract

services/sandbox/
├── Dockerfile                           # OPENCLAUDE_REF and patch audit
├── env_init.sh                          # runtime patch compatibility checks
└── patches/                             # local OpenClaude patches

services/cappycloud_agent/
├── _grpc_session.py                     # receives gRPC events
├── _grpc_event_handlers.py              # normalizes diagnostic events
├── _task_runner.py                      # persists agent_events
└── _pipeline_event_stream.py            # emits SSE events from persisted events

services/api/
├── app/domain/entities.py               # Message payload diagnostic field
├── app/ports/repositories.py            # MessageRepository contract
├── app/application/use_cases/
│   └── conversations.py                 # stream persistence logic
├── app/adapters/secondary/persistence/
│   └── sqlalchemy_message_repo.py       # JSONB mapping
├── app/adapters/primary/http/
│   └── conversations.py                 # thin MessageOut projection
├── app/schemas.py                       # HTTP response schema
├── alembic/versions/                    # migration for message diagnostics
└── tests/                               # unit, adapter, integration coverage

web/
└── src/
    ├── api.ts                           # ChatMessage and SSE event types
    ├── pages/ChatPage.tsx               # diagnostic rendering in active chat
    └── components/chat.module.css       # compact/expanded visual treatment
```

**Structure Decision**: Use the existing message persistence path and chat
timeline instead of a new subsystem. Add one optional sanitized diagnostic field
to assistant messages and one structured stream event. Keep sandbox/OpenClaude
changes isolated to the OpenClaude ref, patch audit, protobuf contract, and
gRPC event normalization.

## Phase 0 Research

See [research.md](research.md). All planning unknowns are resolved. The key
decisions are:

- Pin the sandbox build to the OpenClaude v0.14.0 commit for reproducibility.
- Treat payload diagnostics as structured events, not assistant text.
- Persist diagnostics on the assistant message as JSONB.
- Sanitize to category labels and byte counts only.
- Audit and retire or adjust local OpenClaude patches after the version bump.

## Phase 1 Design

See [data-model.md](data-model.md), [contracts/chat-diagnostics.md](contracts/chat-diagnostics.md), and [quickstart.md](quickstart.md).

Design outputs define:

- `PayloadSizeBreakdown` and safe category fields.
- `Message.payload_diagnostics` persistence and response shape.
- `payload_diagnostic` SSE event shape.
- UI behavior for compact summary, expansion, reload, and absent diagnostics.

## Post-Design Constitution Check

- [x] Spec and plan artifacts exist for this non-trivial runtime/API/frontend change.
- [x] The backend contract change is routed through domain entity, use case,
      repository port, SQL adapter, fake, schema, and thin router projection.
- [x] The diagnostic source is external agent runtime data, normalized through
      the agent bridge before the API exposes it.
- [x] Security posture is explicit: diagnostics carry only safe categories and
      numeric sizes, never raw content or secrets.
- [x] Runtime context stays dynamic; selected repos, model, provider, skills,
      and attachments are measured/summarized per turn, not hardcoded.
- [x] Backend and frontend quality gates are planned.
- [x] No external documentation claims are required beyond the upstream tag/ref
      evidence already recorded in the spec.
- [x] Sandbox rebuild is explicit. No automatic deploy, branch creation, push,
      or production rollout is part of this plan.

## Complexity Tracking

No constitution violations identified.
