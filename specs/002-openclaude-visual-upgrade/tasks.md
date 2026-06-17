# Tasks: OpenClaude v0.14.0 Chat Visual Upgrade

**Input**: Design documents from `specs/002-openclaude-visual-upgrade/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/chat-diagnostics.md](contracts/chat-diagnostics.md), [quickstart.md](quickstart.md)

**Tests**: Required. This feature changes sandbox runtime behavior, gRPC/SSE stream events, API persistence, message history contract, and frontend rendering.

**Organization**: Tasks are grouped by user story so each story can be implemented and validated independently after the shared foundation is complete.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel because it touches different files or only reads/verifies an already completed dependency.
- **[Story]**: User story label, only for user-story phases.
- Every task includes an exact repository path.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Pin the upstream runtime and make local OpenClaude customizations compatible before feature work depends on them.

- [X] T001 Update `OPENCLAUDE_REF` to `66ed9b61dcefea4bd58d1c24011cf32015b0fb29` in `services/sandbox/Dockerfile`
- [X] T002 Audit local patches against OpenClaude v0.14.0 and update, remove, or retain patch files in `services/sandbox/patches/`
- [X] T003 Verify runtime patch assumptions for OpenClaude v0.14.0 in `services/sandbox/env_init.sh`
- [X] T004 Add sandbox-side OpenClaude diagnostic emission to `services/sandbox/patches/multimodal-proto.patch` and `services/sandbox/patches/multimodal-grpc-handler.patch`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Establish the shared event, persistence, and response contracts that block all user stories.

**CRITICAL**: No user story work can begin until this phase is complete.

- [X] T005 Add payload diagnostic protobuf messages and stream event variant in `proto/openclaude.proto`
- [X] T006 Add a nullable JSONB `payload_diagnostics` column migration in `services/api/alembic/versions/20260617_120000_add_message_payload_diagnostics.py`
- [X] T007 Add the `payload_diagnostics` ORM column to the message model in `services/api/app/infrastructure/orm_models.py`
- [X] T008 Add payload diagnostic domain types and the optional `Message.payload_diagnostics` field in `services/api/app/domain/entities.py`
- [X] T009 Add payload diagnostic response schemas and `MessageOut.payload_diagnostics` in `services/api/app/schemas.py`
- [X] T010 Update message repository mapping for the new field in `services/api/app/adapters/secondary/persistence/sqlalchemy_message_repo.py`
- [X] T011 Update the in-memory message fake to preserve `payload_diagnostics` in `services/api/tests/conftest.py`
- [X] T012 Update the internal agent event persistence helper to accept `payload_diagnostic` events in `services/cappycloud_agent/_task_events.py`

**Checkpoint**: Foundation ready. User story implementation can now begin in priority order or in parallel by separate owners.

---

## Phase 3: User Story 1 - Entender peso do pedido no chat (Priority: P1) MVP

**Goal**: Users see a safe, persisted request payload size breakdown in the chat when diagnostic data is available.

**Independent Test**: Run a diagnostic-enabled turn, verify the compact summary shows total payload size plus the three largest safe categories, expand it to see all safe categories, reload the conversation, and confirm the same breakdown remains available. A turn without diagnostics must render exactly as before.

### Tests for User Story 1

- [X] T013 [P] [US1] Add stream use-case tests for valid, absent, duplicate, malformed, and unsafe `payload_diagnostic` events in `services/api/tests/unit/use_cases/test_conversation_streaming.py`
- [X] T014 [P] [US1] Add SQLAlchemy persistence tests for `Message.payload_diagnostics` JSONB round-trip in `services/api/tests/adapter/test_sqlalchemy_sandbox_message_repos.py`
- [X] T015 [P] [US1] Add API integration tests proving message history returns assistant `payload_diagnostics` and omits it for user/no-diagnostic messages in `services/api/tests/integration/test_api_conversations.py`
- [X] T016 [P] [US1] Add agent runtime regression tests for diagnostic event normalization and secret/path stripping in `services/api/tests/unit/test_agent_runtime_regressions.py`

### Implementation for User Story 1

- [X] T017 [US1] Normalize and sanitize OpenClaude diagnostic event data in `services/cappycloud_agent/_grpc_event_handlers.py`
- [X] T018 [US1] Read and dispatch payload diagnostic events from the gRPC stream in `services/cappycloud_agent/_grpc_session.py`
- [X] T019 [US1] Persist normalized `payload_diagnostic` events during task execution in `services/cappycloud_agent/_task_runner.py`
- [X] T020 [US1] Emit `payload_diagnostic` SSE payloads from persisted agent events in `services/cappycloud_agent/_pipeline_event_stream.py`
- [X] T021 [US1] Capture the latest valid diagnostic stream event and save it on the assistant message in `services/api/app/application/use_cases/conversations.py`
- [X] T022 [US1] Ensure payload diagnostics are never included in LLM conversation history in `services/api/app/application/use_cases/conversations.py`
- [X] T023 [US1] Return `payload_diagnostics` from the conversation messages endpoint without adding router business logic in `services/api/app/adapters/primary/http/conversations.py`
- [X] T024 [US1] Add `PayloadSizeCategory`, `PayloadSizeBreakdown`, `ChatMessage.payload_diagnostics`, and `onPayloadDiagnostic` stream typing in `web/src/api.ts`
- [X] T025 [US1] Parse `payload_diagnostic` SSE events and ignore malformed diagnostics in `web/src/api.ts`
- [X] T026 [US1] Attach live and reloaded payload diagnostics to the correct assistant turn in `web/src/pages/ChatPage.tsx`
- [X] T027 [US1] Render compact total plus top three categories and expandable full details in `web/src/pages/ChatPage.tsx`
- [X] T028 [US1] Add diagnostic summary, category row, and expanded-state styles in `web/src/components/chat.module.css`

**Checkpoint**: User Story 1 is functional and testable independently as the MVP.

---

## Phase 4: User Story 2 - Validar estabilidade visual dos estados existentes (Priority: P2)

**Goal**: Existing chat visuals for tool errors, timeouts, human action prompts, progress, resume, usage, and cost remain clear after the OpenClaude update.

**Independent Test**: Simulate or run controlled turns for tool error with stdout, timeout, action-required prompt, resume after compaction, repeated tool failures, and normal completion; confirm existing components remain readable and do not duplicate or get stuck.

### Tests for User Story 2

- [X] T029 [P] [US2] Add stream regression tests for timeout, action-required, done, error, and tool stdout events in `services/api/tests/unit/use_cases/test_conversation_streaming.py`
- [X] T030 [P] [US2] Add agent runtime regression coverage for repeated tool-failure loop and resume/thinking event shapes in `services/api/tests/unit/test_agent_runtime_regressions.py`
- [X] T031 [P] [US2] Add API integration coverage for action-required and error event streaming behavior in `services/api/tests/integration/test_api_conversations.py`

### Implementation for User Story 2

- [X] T032 [US2] Preserve stdout, tool error flags, thinking/resume blocks, and action-required event shapes during v0.14.0 normalization in `services/cappycloud_agent/_grpc_event_handlers.py`
- [X] T033 [US2] Keep timeout, repeated tool-failure, done, and error events terminal and non-duplicated in `services/api/app/application/use_cases/conversations.py`
- [X] T034 [US2] Verify and adjust chat state transitions so spinners clear on timeout/error/done in `web/src/pages/ChatPage.tsx`
- [X] T035 [US2] Verify and adjust existing tool, action-required, thinking, and usage visual treatments after diagnostic UI is added in `web/src/pages/ChatPage.tsx`
- [X] T036 [US2] Document manual visual regression scenarios for these existing states in `specs/002-openclaude-visual-upgrade/quickstart.md`

**Checkpoint**: User Stories 1 and 2 both work without visual regressions.

---

## Phase 5: User Story 3 - Separar mudancas sem impacto visual no chat (Priority: P3)

**Goal**: The team has a reviewable classification proving each OpenClaude v0.14.0 release item is either a new chat visual, validation of an existing visual, or no chat visual impact.

**Independent Test**: Review the v0.14.0 release item matrix and confirm every listed item has exactly one visual scope decision, a rationale, and a corresponding implementation or validation task when needed.

### Tests for User Story 3

- [X] T037 [P] [US3] Add a visual-scope checklist covering every v0.14.0 release item in `specs/002-openclaude-visual-upgrade/checklists/visual-scope.md`

### Implementation for User Story 3

- [X] T038 [US3] Update the release item matrix with implementation outcomes and any changed patch-audit findings in `specs/002-openclaude-visual-upgrade/spec.md`
- [X] T039 [US3] Cross-check the release item matrix against task coverage and acceptance criteria in `specs/002-openclaude-visual-upgrade/tasks.md`
- [X] T040 [US3] Record final no-new-visual decisions and validation notes in `specs/002-openclaude-visual-upgrade/quickstart.md`

**Checkpoint**: All user stories are independently complete and reviewable.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Validate gates, sandbox build, safety review, and documentation before implementation is considered done.

- [X] T041 [P] Run backend lint, format, type, and test gates from `services/api/pyproject.toml`
- [X] T042 [P] Run frontend lint and build gates from `web/package.json`
- [X] T043 Build the sandbox image with the pinned OpenClaude ref using `services/sandbox/Dockerfile`
- [X] T044 Run the manual chat validation scenarios documented in `specs/002-openclaude-visual-upgrade/quickstart.md`
- [X] T045 Review backend diagnostic sanitization for secrets, raw prompts, paths, provider keys, and binary content in `services/cappycloud_agent/_grpc_event_handlers.py`, `services/api/app/application/use_cases/_payload_diagnostics.py`, and `services/api/app/application/use_cases/conversations.py`
- [X] T046 Review frontend diagnostic rendering for secrets, raw prompts, paths, provider keys, and binary content in `web/src/pages/ChatPage.tsx`
- [X] T047 Document any blocked gate, sandbox build failure, or manual validation gap in `specs/002-openclaude-visual-upgrade/quickstart.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on Setup completion and blocks all user stories.
- **User Story 1 (Phase 3)**: Depends on Foundational completion and is the MVP.
- **User Story 2 (Phase 4)**: Depends on Foundational completion; can begin after US1 diagnostic contracts are stable if the same owner is editing shared stream files.
- **User Story 3 (Phase 5)**: Depends on the release item matrix from the spec and can proceed in parallel with US1/US2 after Foundational completion.
- **Polish (Phase 6)**: Depends on all desired user stories being complete.

### User Story Dependencies

- **US1 (P1)**: Requires Setup and Foundational only.
- **US2 (P2)**: Requires Setup and Foundational; shares stream/UI files with US1, so coordinate same-file edits.
- **US3 (P3)**: Requires Setup and Foundational; documentation work can run alongside US1/US2 implementation.

### Within Each User Story

- Tests come before implementation and should fail before code changes when feasible.
- Contract/schema changes come before use-case and adapter changes.
- Agent event normalization comes before API stream persistence.
- API persistence comes before frontend reload rendering.
- Frontend stream typing comes before UI state and rendering changes.

### Parallel Opportunities

- T004 depends on T002 because it implements the sandbox-side diagnostic emission found during patch audit.
- T013-T016 can run in parallel because they target different test files.
- T029-T031 can run in parallel because they target different regression layers.
- T037 can run in parallel with US1 and US2 implementation after the release matrix is stable.
- T041 and T042 can run in parallel after implementation is complete.

---

## Parallel Example: User Story 1

```bash
# Backend/API/agent tests can be prepared together:
Task: "T013 Add stream use-case tests in services/api/tests/unit/use_cases/test_conversation_streaming.py"
Task: "T014 Add SQLAlchemy persistence tests in services/api/tests/adapter/test_sqlalchemy_sandbox_message_repos.py"
Task: "T015 Add API integration tests in services/api/tests/integration/test_api_conversations.py"
Task: "T016 Add agent runtime regression tests in services/api/tests/unit/test_agent_runtime_regressions.py"
```

## Parallel Example: User Story 2

```bash
# Existing visual-state regression coverage can be prepared together:
Task: "T029 Add stream regression tests in services/api/tests/unit/use_cases/test_conversation_streaming.py"
Task: "T030 Add agent runtime regression tests in services/api/tests/unit/test_agent_runtime_regressions.py"
Task: "T031 Add API integration tests in services/api/tests/integration/test_api_conversations.py"
```

## Parallel Example: User Story 3

```bash
# Documentation review can proceed while implementation stabilizes:
Task: "T037 Add visual-scope checklist in specs/002-openclaude-visual-upgrade/checklists/visual-scope.md"
Task: "T040 Record final no-new-visual decisions in specs/002-openclaude-visual-upgrade/quickstart.md"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 and Phase 2.
2. Complete Phase 3 only.
3. Validate diagnostic-enabled, no-diagnostic, unsafe diagnostic, and reload scenarios.
4. Stop and demo the compact payload diagnostic in chat before broadening regression scope.

### Incremental Delivery

1. Setup + Foundational establish OpenClaude v0.14.0, protobuf, storage, and API contract.
2. US1 delivers the only new chat visual and persisted reload behavior.
3. US2 hardens existing visual states against runtime changes from v0.14.0.
4. US3 closes the release-scope review loop so no release item is left ambiguous.
5. Polish runs gates, sandbox build, manual scenarios, and safety review.

### Parallel Team Strategy

1. One owner handles sandbox pin and patch audit.
2. One owner handles protobuf, agent stream, API persistence, and backend tests.
3. One owner handles frontend stream typing, state, and rendering.
4. One owner handles release matrix/checklist and manual validation.

## Notes

- Use the `create-migration` skill when implementing T006 and verify the generated revision matches `services/api/alembic/versions/20260617_120000_add_message_payload_diagnostics.py` or update this task to the generated file name before committing.
- Do not push images, deploy containers, or roll production services without a separate explicit request.
- Do not add raw prompt text, tool payloads, file paths, provider keys, or binary data to diagnostics.
- Keep routers thin; diagnostic decisions belong in use cases, schemas, ports/adapters, and the agent bridge.

## Coverage Cross-Check

- New diagnostic visual is covered by T013-T028 and the contract in `contracts/chat-diagnostics.md`.
- Existing timeout/error/action/tool/thinking visual stability is covered by T029-T036.
- No-new-visual release decisions are covered by T037-T040 and the matrix in `spec.md`.
- Sandbox ref and patch compatibility are covered by T001-T004 plus the patch-apply validation documented in `quickstart.md`.
