# Tasks: OpenClaude v0.24 Chat Commands

**Input**: Design documents from `specs/008-openclaude-v024-chat-commands/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md`

**Tests**: This feature changes backend contracts, runtime adapters, sandbox build, agent stream mapping and frontend chat UX. Include focused tests for each code change plus the backend, frontend and sandbox gates listed below.

**Organization**: Tasks are grouped by user story so each story can be implemented and validated independently after the shared foundation.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel because it touches different files and does not depend on incomplete tasks.
- **[Story]**: User story label for story phases only.
- Every task includes exact CappyCloud file paths.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Capture the current baseline, release target and local runtime patch surface before implementation.

- [X] T001 Verify OpenClaude tag `v0.24.0` with `git ls-remote --tags https://github.com/Gitlawb/openclaude.git refs/tags/v0.24.0` and record the observed commit in `specs/008-openclaude-v024-chat-commands/quickstart.md`
- [X] T002 [P] Capture current sandbox runtime evidence from `services/sandbox/Dockerfile`, `services/sandbox/env_init.sh` and `services/sandbox/patches/` in `specs/008-openclaude-v024-chat-commands/runtime-audit.md`
- [X] T003 [P] Capture current chat composer and stream baseline from `web/src/pages/ChatPage.tsx`, `web/src/api.ts` and `web/src/components/ThinkingStream.tsx` in `specs/008-openclaude-v024-chat-commands/ui-baseline.md`
- [X] T004 [P] Capture current backend conversation and sandbox-runtime boundaries from `services/api/app/adapters/primary/http/conversations.py`, `services/api/app/application/use_cases/conversations.py`, `services/api/app/ports/sandbox_runtime.py` and `services/api/app/adapters/secondary/sandbox_runtime/docker_sidecar.py` in `specs/008-openclaude-v024-chat-commands/backend-baseline.md`
- [X] T005 [P] Create a release impact validation checklist for all v0.18.0-v0.24.0 themes in `specs/008-openclaude-v024-chat-commands/release-impact-checklist.md`
- [X] T006 [P] Create a manual smoke checklist for command discovery, command execution, streaming, cancellation, action-required, attachments, fallback model, usage and cost in `specs/008-openclaude-v024-chat-commands/manual-smoke.md`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Define shared contracts, ports, fakes, real adapters and stream types that all stories depend on.

**Critical**: No user story work should begin until this phase is complete.

- [X] T007 Define command domain value objects for slash commands, arguments, availability, catalog and execution events in `services/api/app/domain/chat_commands.py`
- [X] T008 Define the `ChatCommandRuntimePort` protocol for runtime command discovery/execution in `services/api/app/ports/chat_commands.py`
- [X] T009 Define the `ModelProfileLookupPort` protocol for authorized model/profile lookup used by `/model` commands in `services/api/app/ports/model_profiles.py`
- [X] T010 Implement the real sandbox command adapter client wiring and health/error handling in `services/api/app/adapters/secondary/sandbox_runtime/chat_commands.py`
- [X] T011 Implement the real model profile adapter using existing AI model access data in `services/api/app/adapters/secondary/persistence/sqlalchemy_model_profiles.py`
- [X] T012 [P] Implement in-memory fake command runtime and fake model profile lookup in `services/api/tests/fakes_chat_commands.py`
- [X] T013 [P] Add contract tests for `ChatCommandRuntimePort` behavior in `services/api/tests/contract/test_chat_command_runtime_port.py`
- [X] T014 [P] Add contract tests for `ModelProfileLookupPort` behavior in `services/api/tests/contract/test_model_profiles_port.py`
- [X] T015 Define API schemas for command catalog, arguments, availability, execution request and execution response in `services/api/app/schemas_chat_commands.py`
- [X] T016 Implement command sanitization helpers for diagnostics, paths, URLs, OAuth callbacks, tool arguments and sensitive arguments in `services/api/app/application/use_cases/chat_command_sanitization.py`
- [X] T017 Add unit tests for command sanitization edge cases in `services/api/tests/unit/use_cases/test_chat_command_sanitization.py`
- [X] T018 Implement backend use cases for listing commands and revalidating availability in `services/api/app/application/use_cases/chat_commands.py`
- [X] T019 Implement backend use case for command execution decisions, missing arguments, confirmation and unavailable responses in `services/api/app/application/use_cases/chat_command_execution.py`
- [X] T020 Add unit tests for command catalog authorization, unavailable reasons and confirmation classification in `services/api/tests/unit/use_cases/test_chat_commands.py`
- [X] T021 Add unit tests for command execution blocking, confirmation and sensitive argument handling in `services/api/tests/unit/use_cases/test_chat_command_execution.py`
- [X] T022 Add thin HTTP routes for `GET /api/conversations/{conversation_id}/commands` and `POST /api/conversations/{conversation_id}/commands/execute` in `services/api/app/adapters/primary/http/conversation_commands.py`
- [X] T023 Register the conversation command router in `services/api/app/main.py`
- [X] T024 [P] Add HTTP integration tests for command catalog and execution responses in `services/api/tests/integration/test_api_conversation_commands.py`
- [X] T025 Define frontend TypeScript types and API helpers for command catalog/execution in `web/src/api.ts`
- [ ] T026 [P] Add frontend API unit tests for command parsing and error formatting in `web/src/api.test.ts`
- [X] T027 Extend stream event typing for `command_start` and `command_result` in `web/src/api.ts`
- [X] T028 Extend agent event mapping for command events without breaking existing `status`, `text`, `tool_start`, `tool_result`, `action_required`, `payload_diagnostic`, `done` and `error` events in `services/cappycloud_agent/_grpc_event_handlers.py`
- [X] T029 Add unit tests for command stream event mapping in `services/api/tests/unit/use_cases/test_conversation_streaming.py`
- [X] T030 Update `docs/ARCHITECTURE.md` to document command discovery/execution boundaries and the rule that CappyCloud remains source of truth for conversation, model, permission, tokens and cost

**Checkpoint**: Ports have real adapters, fakes and contract tests; API and stream contracts are ready for story work.

---

## Phase 3: User Story 1 - Executar comandos slash pelo chat (Priority: P1) MVP

**Goal**: Users can type `/` in the chat input, discover upstream commands with Portuguese descriptions and availability, and execute supported commands safely through the CappyCloud chat.

**Independent Test**: Open a conversation, type `/`, filter suggestions, select commands with and without arguments, confirm state-changing commands, and verify timeline states without losing draft, attachments, selected model or permission mode.

### Tests for User Story 1

- [X] T031 [P] [US1] Add backend test for command catalog including all discovered upstream command names and unavailable states in `services/api/tests/unit/use_cases/test_chat_commands.py`
- [X] T032 [P] [US1] Add backend test for command execution result statuses `started`, `waiting_for_input`, `completed`, `unavailable`, `failed` and `cancelled` in `services/api/tests/unit/use_cases/test_chat_command_execution.py`
- [ ] T033 [P] [US1] Add frontend tests for slash trigger rules, filtering and draft preservation in `web/src/components/chat/SlashCommandMenu.test.tsx`
- [ ] T034 [P] [US1] Add frontend tests for keyboard/pointer selection and unavailable command behavior in `web/src/components/chat/SlashCommandMenu.test.tsx`
- [ ] T035 [P] [US1] Add frontend tests for inline confirmation behavior in `web/src/components/chat/CommandConfirmation.test.tsx`
- [ ] T036 [P] [US1] Add frontend tests for command timeline rendering in `web/src/components/ThinkingStream.test.tsx`

### Implementation for User Story 1

- [X] T037 [US1] Implement upstream command discovery source in `services/api/app/adapters/secondary/sandbox_runtime/chat_commands.py` using OpenClaude v0.24 runtime metadata, static introspection or sandbox adapter evidence
- [X] T038 [US1] Add a checked-in command catalog seed for v0.24 fallback discovery in `services/sandbox/openclaude-v024-commands.json`
- [X] T039 [US1] Map command categories, Portuguese descriptions, arguments and availability states in `services/api/app/application/use_cases/chat_commands.py`
- [X] T040 [US1] Implement safe execution mappings for the initial supported command families, including `/ctx` and `/cost` sourcing provider usage and authorized pricing, in `services/api/app/application/use_cases/chat_command_execution.py`
- [X] T041 [US1] Implement unavailable execution responses for terminal-only, unsafe, unauthorized and unmapped upstream commands in `services/api/app/application/use_cases/chat_command_execution.py`
- [X] T042 [US1] Implement inline confirmation classification for state, cost, model, context, runtime, branch, session and external-access commands in `services/api/app/application/use_cases/chat_command_execution.py`
- [X] T043 [US1] Implement command result emission through existing conversation stream helpers in `services/api/app/application/use_cases/_stream_helpers.py`
- [X] T044 [US1] Implement command event forwarding in `services/cappycloud_agent/_grpc_session.py`
- [X] T045 [US1] Create slash command menu component with filtering, disabled rows, argument hints and availability reasons in `web/src/components/chat/SlashCommandMenu.tsx`
- [X] T046 [US1] Create inline confirmation component for command execution in `web/src/components/chat/CommandConfirmation.tsx`
- [X] T047 [US1] Integrate slash trigger at input start or after newline in the active composer in `web/src/pages/ChatPage.tsx`
- [X] T048 [US1] Preserve attachments, multiline drafts, selected model, permission mode and pending action-required prompts while slash suggestions open/close, and close/refetch suggestions when conversation, model, permission or runtime changes, in `web/src/pages/ChatPage.tsx`
- [X] T049 [US1] Keep composer footer, send/stop action, runtime warning, attachment state and permission controls mounted while suggestions are open in `web/src/pages/ChatPage.tsx`
- [X] T050 [US1] Render command start/result/unavailable/failed/cancelled timeline states through `web/src/pages/ChatPage.tsx` and `web/src/components/ThinkingStream.tsx`
- [X] T051 [US1] Add CSS for responsive suggestion layout, focus states and narrow viewport safety in `web/src/components/chat/SlashCommandMenu.module.css`
- [X] T052 [US1] Add accessible Portuguese labels and announcements for command availability, confirmation and disabled reasons in `web/src/components/chat/SlashCommandMenu.tsx`
- [X] T053 [US1] Add client-side performance measurement for slash catalog open time and filtering time in `web/src/components/chat/SlashCommandMenu.tsx`
- [ ] T054 [US1] Record manual validation results for SC-002, SC-003, SC-005, SC-006 and SC-007 in `specs/008-openclaude-v024-chat-commands/manual-smoke.md`

**Checkpoint**: User Story 1 is independently demoable as MVP.

---

## Phase 4: User Story 2 - Atualizar runtime para OpenClaude v0.24.0 com rastreabilidade (Priority: P2)

**Goal**: Sandbox builds against OpenClaude `v0.24.0` with patch decisions documented and CappyCloud-owned model, permission, history, usage and cost behavior preserved.

**Independent Test**: Verify the pinned commit, build the sandbox image, run a conversation smoke, and confirm model, permission, history, usage and cost remain controlled by CappyCloud.

### Tests for User Story 2

- [X] T055 [P] [US2] Add unit test asserting sandbox Dockerfile target commit evidence in `services/api/tests/unit/test_openclaude_runtime_pin.py`
- [X] T056 [P] [US2] Add runtime patch audit test for required patch decisions in `services/api/tests/unit/test_openclaude_patch_audit.py`
- [X] T057 [P] [US2] Add sandbox permission/model override regression test in `services/api/tests/unit/test_sandbox_permission_patch.py`
- [X] T058 [P] [US2] Add agent usage/final model regression test in `services/api/tests/unit/use_cases/test_conversation_streaming.py`

### Implementation for User Story 2

- [X] T059 [US2] Update `OPENCLAUDE_REF` to `2ff93a10bf88ab6d7030fc4ade5316a7424fa2f9` in `services/sandbox/Dockerfile`
- [X] T060 [US2] Audit `services/sandbox/patches/grep-tool-n-alias.patch` against v0.24.0 and record retained/changed/removed/obsolete in `specs/008-openclaude-v024-chat-commands/runtime-audit.md`
- [X] T061 [US2] Audit `services/sandbox/patches/multimodal-proto.patch` against v0.24.0 and record retained/changed/removed/obsolete in `specs/008-openclaude-v024-chat-commands/runtime-audit.md`
- [X] T062 [US2] Audit `services/sandbox/patches/multimodal-grpc-handler.patch` against v0.24.0 and record retained/changed/removed/obsolete in `specs/008-openclaude-v024-chat-commands/runtime-audit.md`
- [X] T063 [US2] Audit `services/sandbox/patches/read-empty-pages.patch` against v0.24.0 and record retained/changed/removed/obsolete in `specs/008-openclaude-v024-chat-commands/runtime-audit.md`
- [X] T064 [US2] Audit `services/sandbox/patches/worktree-tool-guard.patch`, `services/sandbox/patches/mcp-grpc-integration.patch`, `services/sandbox/patches/numeric-parameter-grep-wrapper.patch` and `services/sandbox/patches/numeric-parameter-grep-guard.patch` against v0.24.0 in `specs/008-openclaude-v024-chat-commands/runtime-audit.md`
- [X] T065 [US2] Audit inline provider, context, usage, Azure, dynamic model and session startup edits in `services/sandbox/env_init.sh` against v0.24.0 in `specs/008-openclaude-v024-chat-commands/runtime-audit.md`
- [X] T066 [US2] Update or remove obsolete patch applications in `services/sandbox/Dockerfile`
- [X] T067 [US2] Update runtime startup compatibility in `services/sandbox/env_init.sh` for OpenClaude v0.24.0
- [X] T068 [US2] Update sandbox runtime health/status checks so `openclaude` is not reported running when gRPC port `50051` is closed in `services/sandbox/runtime_handler.js`
- [X] T069 [US2] Update session server runtime status aggregation to use real OpenClaude health in `services/sandbox/session_server.js`
- [X] T070 [US2] Rebuild sandbox image with `docker build --build-arg OPENCLAUDE_REF=2ff93a10bf88ab6d7030fc4ade5316a7424fa2f9 -f services/sandbox/Dockerfile -t cappycloud-sandbox:openclaude-v024-check .` and record output summary in `specs/008-openclaude-v024-chat-commands/runtime-audit.md`
- [ ] T071 [US2] Run sandbox smoke for normal response, tool event, action-required, cancellation and command catalog discovery, then record results in `specs/008-openclaude-v024-chat-commands/runtime-audit.md`
- [X] T072 [US2] Verify no production image push or deployment step is performed and document rollout exclusion in `specs/008-openclaude-v024-chat-commands/runtime-audit.md`

**Checkpoint**: Runtime upgrade is locally buildable and traceable, without authorizing production deployment.

---

## Phase 5: User Story 3 - Decidir impacto de UI de cada release recente (Priority: P3)

**Goal**: Every relevant OpenClaude release theme from v0.18.0 through v0.24.0 has a CappyCloud UI/runtime decision, validation requirement and implementation link.

**Independent Test**: Compare the matrix against release notes and confirm every command family and release theme has a decision, rationale and validation task or explicit out-of-scope reason.

### Tests for User Story 3

- [X] T073 [P] [US3] Add checklist validation for all v0.18.0-v0.24.0 release themes in `specs/008-openclaude-v024-chat-commands/release-impact-checklist.md`
- [X] T074 [P] [US3] Add release impact completeness test script in `specs/008-openclaude-v024-chat-commands/scripts/check-release-impact.ps1`

### Implementation for User Story 3

- [X] T075 [US3] Verify and refine the release impact table from `specs/008-openclaude-v024-chat-commands/spec.md` into a traceable implementation-readiness matrix in `specs/008-openclaude-v024-chat-commands/release-impact-matrix.md`
- [X] T076 [US3] Link each command family to backend/frontend/runtime tasks in `specs/008-openclaude-v024-chat-commands/release-impact-matrix.md`
- [X] T077 [US3] Document out-of-scope terminal-only, provider enablement, production update and OAuth callback decisions in `specs/008-openclaude-v024-chat-commands/release-impact-matrix.md`
- [X] T078 [US3] Document UI validation decisions for model picker, context window, cost/context diagnostics, bughunter, reports, repo map, background sessions, goal/session controls, update/runtime and doctor diagnostics in `specs/008-openclaude-v024-chat-commands/release-impact-matrix.md`
- [X] T079 [US3] Run `specs/008-openclaude-v024-chat-commands/scripts/check-release-impact.ps1` and record results in `specs/008-openclaude-v024-chat-commands/release-impact-checklist.md`

**Checkpoint**: Release impact matrix is complete and independently reviewable.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Security, accessibility, performance, docs and quality gates across all stories.

- [X] T080 [P] Add security regression tests for command error redaction and unauthorized repository content blocking in `services/api/tests/unit/use_cases/test_chat_command_sanitization.py`
- [ ] T081 [P] Add frontend accessibility regression tests for keyboard focus, disabled state announcements and confirmation cancellation in `web/src/components/chat/SlashCommandMenu.test.tsx`
- [ ] T082 [P] Add frontend narrow viewport regression coverage for composer and suggestions in `web/src/components/chat/SlashCommandMenu.test.tsx`
- [X] T083 [P] Update `docs/how-to/debug-agent.md` with real gRPC health checks and misleading sidecar status remediation
- [X] T084 Update `specs/008-openclaude-v024-chat-commands/quickstart.md` with final command catalog, sandbox build and manual smoke outcomes
- [ ] T085 Run backend gates `ruff check .`, `ruff format --check .`, `mypy app/` and `pytest` from `services/api`, then record pass/fail evidence in `specs/008-openclaude-v024-chat-commands/manual-smoke.md`
- [X] T086 Run frontend gates `pnpm run lint` and `pnpm run build` from `web`, then record pass/fail evidence in `specs/008-openclaude-v024-chat-commands/manual-smoke.md`
- [X] T087 Run sandbox build and smoke validation from `specs/008-openclaude-v024-chat-commands/quickstart.md`, then record pass/fail evidence in `specs/008-openclaude-v024-chat-commands/runtime-audit.md`
- [X] T088 Run release impact completeness script and command catalog completeness checks, then record pass/fail evidence in `specs/008-openclaude-v024-chat-commands/release-impact-checklist.md`
- [X] T089 Review changed files for secrets, raw OAuth callbacks, raw provider logs, generated dumps and unauthorized repository content before marking the feature complete
- [X] T090 Re-run `$speckit-analyze` after implementation artifacts are updated to confirm spec, plan and tasks remain consistent

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on Phase 1 and blocks all user stories.
- **User Story 1 (Phase 3)**: Depends on Phase 2 and is the MVP.
- **User Story 2 (Phase 4)**: Depends on Phase 2; can run in parallel with US1 after shared contracts exist, but final command discovery validation benefits from US1.
- **User Story 3 (Phase 5)**: Depends on Phase 1; can run in parallel with implementation once the matrix format exists.
- **Polish (Phase 6)**: Depends on the desired stories being complete.

### User Story Dependencies

- **US1 (P1)**: Starts after Phase 2; no dependency on US2 or US3 for MVP behavior, using the v0.24 command seed if runtime upgrade is still in progress.
- **US2 (P2)**: Starts after Phase 2; independent runtime upgrade with shared command port/adapter contracts.
- **US3 (P3)**: Starts after Phase 1; independent documentation/validation matrix, but final links should reference US1 and US2 tasks.

### Within Each User Story

- Tests precede implementation.
- Domain and ports precede use cases.
- Use cases precede HTTP routes and frontend integration.
- Runtime patch audit precedes Dockerfile patch changes.
- UI components precede ChatPage integration.
- Validation evidence is recorded before the story checkpoint is considered complete.

## Parallel Opportunities

- Setup evidence tasks T002-T006 can run in parallel.
- Foundational tests T012-T014 can run in parallel with schema/type work T015 and frontend type work T025-T027 after ports are named.
- US1 tests T031-T036 can run in parallel.
- US2 audit tasks T060-T065 can run in parallel after T059 is prepared on a separate branch or worktree.
- US3 validation tasks T073-T074 can run in parallel.
- Polish tests/docs T080-T083 can run in parallel.

## Parallel Example: User Story 1

```text
Task: T033 Add frontend tests for slash trigger rules, filtering and draft preservation in web/src/components/chat/SlashCommandMenu.test.tsx
Task: T034 Add frontend tests for keyboard/pointer selection and unavailable command behavior in web/src/components/chat/SlashCommandMenu.test.tsx
Task: T035 Add frontend tests for inline confirmation behavior in web/src/components/chat/CommandConfirmation.test.tsx
Task: T036 Add frontend tests for command timeline rendering in web/src/components/ThinkingStream.test.tsx
Task: T031 Add backend test for command catalog including all discovered upstream command names and unavailable states in services/api/tests/unit/use_cases/test_chat_commands.py
```

## Parallel Example: User Story 2

```text
Task: T060 Audit services/sandbox/patches/grep-tool-n-alias.patch against v0.24.0
Task: T061 Audit services/sandbox/patches/multimodal-proto.patch against v0.24.0
Task: T062 Audit services/sandbox/patches/multimodal-grpc-handler.patch against v0.24.0
Task: T063 Audit services/sandbox/patches/read-empty-pages.patch against v0.24.0
Task: T064 Audit remaining patch files against v0.24.0
Task: T065 Audit inline edits in services/sandbox/env_init.sh against v0.24.0
```

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 setup evidence.
2. Complete Phase 2 foundation, including ports, real adapters, fakes and contract tests.
3. Complete Phase 3 US1.
4. Validate command discovery and safe execution through the chat UI.
5. Stop for review before broad runtime rollout.

### Incremental Delivery

1. Foundation ready.
2. US1 delivers slash command UX and safe command contract.
3. US2 upgrades and validates the sandbox runtime pin to OpenClaude v0.24.0.
4. US3 completes release impact traceability and product decisions.
5. Polish runs gates and records evidence.

### Team Strategy

1. One developer owns backend use cases/contracts.
2. One developer owns frontend composer/timeline UX.
3. One developer owns sandbox runtime upgrade and patch audit.
4. One reviewer owns release-impact traceability and security redaction checks.

## Completion Summary

- **Total tasks**: 90
- **Setup**: 6
- **Foundational**: 24
- **US1**: 24
- **US2**: 18
- **US3**: 7
- **Polish**: 11
- **Parallel opportunities**: 26 tasks marked `[P]`
- **Suggested MVP scope**: Phase 1, Phase 2 and User Story 1
- **Format validation**: All task rows use `- [ ] T###`, optional `[P]`, story labels only in user story phases, and concrete file paths or explicit commands
