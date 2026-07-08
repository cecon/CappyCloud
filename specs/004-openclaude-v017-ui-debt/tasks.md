# Tasks: OpenClaude v0.17.1 UI Debt Audit

**Input**: Design documents from `specs/004-openclaude-v017-ui-debt/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Required for code changes. Backend changes must cover `ruff`,
`mypy`, and `pytest`; frontend changes must cover `web/` lint/build; sandbox
changes must include a Docker build or documented blocker.

**Organization**: Tasks are grouped by user story so each story can be
implemented and validated independently.

## Phase 1: Setup

**Purpose**: Establish the runtime target and review surface before behavior
changes.

- [X] T001 Update `OPENCLAUDE_REF` to `1b7e55058cca57f2f83d7e229441631794286c1a` in `services/sandbox/Dockerfile`
- [X] T002 [P] Create patch audit notes for all files in `services/sandbox/patches/` in `specs/004-openclaude-v017-ui-debt/quickstart.md`
- [X] T003 [P] Record the v0.17.1 runtime pin and out-of-scope v0.18.0 decision in `docs/how-to/agent-runtime-context.md`
- [X] T004 [P] Add a sandbox build validation command for the pinned runtime in `specs/004-openclaude-v017-ui-debt/quickstart.md`

---

## Phase 2: Foundational

**Purpose**: Protect shared contracts before user-story work starts.

- [X] T005 Review OpenClaude v0.17.1 source compatibility against `proto/openclaude.proto`
- [X] T006 Review OpenClaude v0.17.1 source compatibility against `services/sandbox/patches/multimodal-grpc-handler.patch`
- [X] T007 Review OpenClaude v0.17.1 source compatibility against `services/sandbox/patches/multimodal-proto.patch`
- [X] T008 Review OpenClaude v0.17.1 source compatibility against `services/sandbox/patches/grep-tool-n-alias.patch`
- [X] T009 Review OpenClaude v0.17.1 source compatibility against `services/sandbox/patches/read-empty-pages.patch`
- [X] T010 [P] Add or update unit coverage for sanitized gRPC diagnostics in `services/api/tests/unit/test_agent_runtime_regressions.py`
- [X] T011 [P] Add or update unit coverage for permission-mode forwarding in `services/api/tests/unit/test_agent_permission_mode.py`
- [X] T012 [P] Add or update frontend stream event type coverage in `web/src/api.ts`
- [X] T013 Confirm no persistence migration is required for new entities in `services/api/alembic/versions/`

**Checkpoint**: Runtime pin, patch audit, and shared event assumptions are ready.

---

## Phase 3: User Story 1 - Mapear impacto visual do salto para v0.17.1 (Priority: P1) MVP

**Goal**: Every release item has a CappyCloud UI decision and the runtime can be
built from the v0.17.1 pin with audited patches.

**Independent Test**: Review the release matrix and build the sandbox image from
the pinned SHA.

### Tests for User Story 1

- [X] T014 [P] [US1] Add a regression test for tool error visibility after mixed stream events in `services/api/tests/unit/test_agent_runtime_regressions.py`
- [X] T015 [P] [US1] Add frontend validation for tool/activity/error rendering states in `web/src/pages/ChatPage.tsx`

### Implementation for User Story 1

- [X] T016 [US1] Apply retained/changed patch decisions to `services/sandbox/patches/`
- [X] T017 [US1] Build the sandbox image from `services/sandbox/Dockerfile` using the v0.17.1 `OPENCLAUDE_REF`
- [X] T018 [P] [US1] Update the release-item matrix outcomes in `specs/004-openclaude-v017-ui-debt/spec.md`
- [X] T019 [P] [US1] Document manual visual validation results in `specs/004-openclaude-v017-ui-debt/quickstart.md`
- [X] T020 [US1] Verify startup/runtime diagnostics remain sanitized in `services/cappycloud_agent/_grpc_event_handlers.py`

**Checkpoint**: User Story 1 is independently demonstrable with a pinned runtime
and audited UI decisions.

---

## Phase 4: User Story 2 - Preservar continuidade de conversa e sessao (Priority: P2)

**Goal**: Conversation history, resume, permission mode, progress, and terminal
states remain CappyCloud-owned after OpenClaude v0.17.1.

**Independent Test**: Switch between two conversations, reload the page, resume
a session, and verify the active conversation state is correct.

### Tests for User Story 2

- [X] T021 [P] [US2] Add backend regression coverage for persisted `Conversation.permission_mode` during stream requests in `services/api/tests/integration/test_api_conversations.py`
- [X] T022 [P] [US2] Add backend regression coverage for session resume state isolation in `services/api/tests/unit/test_agent_runtime_regressions.py`
- [X] T023 [P] [US2] Add frontend validation for conversation switch while streaming or filtered in `web/src/pages/ChatPage.tsx`

### Implementation for User Story 2

- [X] T024 [US2] Confirm `StreamMessage` keeps CappyCloud as source of truth in `services/api/app/application/use_cases/conversations.py`
- [X] T025 [US2] Confirm `permission_mode` is sent on each gRPC request in `services/cappycloud_agent/_grpc_session.py`
- [X] T026 [US2] Constrain or disable OpenClaude cache/session persistence in `services/sandbox/patches/multimodal-grpc-handler.patch`
- [X] T027 [US2] Preserve active-conversation state on reload and switch in `web/src/pages/ChatPage.tsx`
- [X] T028 [US2] Validate cancellation and `ActionRequired` resume behavior in `services/cappycloud_agent/_grpc_session.py`

**Checkpoint**: User Story 2 works without relying on OpenClaude visible cache
or session history.

---

## Phase 5: User Story 3 - Tornar fallback de provider e catalogo de modelos confiaveis (Priority: P3)

**Goal**: Users can trust selected/final model, authorized fallback, capability
state, and cost after the runtime upgrade.

**Independent Test**: Simulate normal execution, authorized fallback,
unauthorized fallback, retired model, and vision mismatch.

### Tests for User Story 3

- [X] T029 [P] [US3] Add backend test for authorized model access during stream requests in `services/api/tests/integration/test_api_conversations.py`
- [X] T030 [P] [US3] Add backend test for provider-returned usage/cost persistence in `services/api/tests/unit/use_cases/test_conversation_payload_diagnostics.py`
- [X] T031 [P] [US3] Add frontend validation for retired/unavailable model states in `web/src/pages/ChatPage.tsx`
- [X] T032 [P] [US3] Add admin catalog validation for provider/model metadata in `web/src/pages/AdminModelsPage.tsx`

### Implementation for User Story 3

- [X] T033 [US3] Add sanitized final-model/fallback metadata handling in `services/cappycloud_agent/_grpc_event_handlers.py`
- [X] T034 [US3] Enforce authorized final model behavior in `services/api/app/application/use_cases/conversations.py`
- [X] T035 [US3] Ensure provider usage and catalog pricing remain the cost source in `services/api/app/application/use_cases/conversations.py`
- [X] T036 [US3] Render sanitized fallback/final-model indication in `web/src/pages/ChatPage.tsx`
- [X] T037 [US3] Keep model picker visibility governed by authorized catalog data in `web/src/pages/ChatPage.tsx`
- [X] T038 [US3] Validate provider sync/admin wording for dynamic catalogs in `web/src/pages/AdminProvidersPage.tsx`

**Checkpoint**: User Story 3 shows trustworthy model/cost state without silent
unauthorized fallback.

---

## Final Phase: Polish & Cross-Cutting Concerns

**Purpose**: Finish validation, documentation, and gates.

- [X] T039 [P] Update architecture notes for the v0.17.1 runtime pin in `docs/ARCHITECTURE.md`
- [X] T040 [P] Update runtime context docs for fallback/session/skill-source decisions in `docs/how-to/agent-runtime-context.md`
- [X] T041 [P] Validate `skill://` provenance decisions in `web/src/components/sandbox-globals/SandboxSkillsPanel.tsx`
- [X] T042 [P] Validate conversation search states from the quickstart in `web/src/pages/ChatPage.tsx`
- [X] T043 Run `ruff check .` and `ruff format --check .` from `services/api/`
- [ ] T044 Run `mypy app/` from `services/api/`
- [ ] T045 Run `pytest` from `services/api/`
- [X] T046 Run `pnpm --dir web lint`
- [X] T047 Run `pnpm --dir web build`
- [X] T048 Run or document the sandbox Docker build from `services/sandbox/Dockerfile`
- [X] T049 Record any blocked validation or gate result in `specs/004-openclaude-v017-ui-debt/quickstart.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- Setup has no dependencies.
- Foundational depends on Setup and blocks all user stories.
- User Story 1 depends on Foundational and is the MVP.
- User Story 2 depends on Foundational and can proceed after US1 patch/build
  assumptions are known.
- User Story 3 depends on Foundational and can proceed independently of US2,
  except for shared stream metadata decisions.
- Final Phase depends on all desired user stories.

### User Story Dependencies

- US1: No dependency on other stories after Foundational.
- US2: Depends on shared runtime/event assumptions; no product dependency on
  US3.
- US3: Depends on shared runtime/event assumptions; no product dependency on
  US2.

### Parallel Opportunities

- T002, T003, and T004 can run in parallel.
- T010, T011, and T012 can run in parallel.
- T014 and T015 can run in parallel.
- T018 and T019 can run in parallel after T016/T017.
- T021, T022, and T023 can run in parallel.
- T029, T030, T031, and T032 can run in parallel.
- T039, T040, T041, and T042 can run in parallel.

---

## Parallel Example: User Story 2

```text
Task: "Add backend regression coverage for persisted Conversation.permission_mode during stream requests in services/api/tests/integration/test_api_conversations.py"
Task: "Add backend regression coverage for session resume state isolation in services/api/tests/unit/test_agent_runtime_regressions.py"
Task: "Add frontend validation for conversation switch while streaming or filtered in web/src/pages/ChatPage.tsx"
```

---

## Implementation Strategy

### MVP First

1. Complete Setup and Foundational.
2. Complete US1.
3. Validate the sandbox build and release matrix before editing broader UI/API
   behavior.

### Incremental Delivery

1. Runtime pin and patch audit.
2. Conversation/session source-of-truth safeguards.
3. Provider fallback/model catalog correctness.
4. Docs, quickstart evidence, and quality gates.

### Stop Conditions

- Stop if v0.17.1 source no longer matches patch assumptions and patch intent
  cannot be preserved.
- Stop if OpenClaude fallback metadata cannot be sanitized enough to support
  the US3 UI contract.
- Stop if sandbox build requires production rollout or container replacement
  outside this feature scope.
