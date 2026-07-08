# Tasks: OpenClaude v0.15.0 Permission Mode Upgrade

**Input**: Design documents from `specs/003-openclaude-v015-ui-audit/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md`

**Tests**: Required. This feature changes backend contracts, persistence, frontend chat UI, agent pipeline, protobuf/gRPC, and sandbox patches.

**Organization**: Tasks are grouped by user story so each story can be implemented and validated independently after the foundational phase.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm the implementation target and the local surfaces that will be changed.

- [X] T001 Verify the current OpenClaude runtime pin and record the v0.14.0 to v0.15.0 upgrade scope in `specs/003-openclaude-v015-ui-audit/quickstart.md`
- [X] T002 [P] Re-verify the `v0.15.0` tag SHA `670744fc70353f2270e86531dffa1c06f4fac79c` and source release links in `specs/003-openclaude-v015-ui-audit/quickstart.md`
- [X] T003 [P] Inspect the existing chat toolbar and compact control patterns in `web/src/pages/ChatPage.tsx` and `web/src/components/chat.module.css`
- [X] T004 [P] Inventory local OpenClaude patches from `services/sandbox/patches/` and add the audit checklist location to `specs/003-openclaude-v015-ui-audit/quickstart.md`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Add the shared permission-mode contract used by API, frontend, agent runtime, and sandbox.

**Critical**: No user story implementation should begin until this phase is complete.

- [X] T005 [P] Add failing permission-mode enum validation tests in `services/api/tests/unit/domain/test_value_objects.py`
- [X] T006 [P] Add failing pipeline body tests for default and explicit `permission_mode` in `services/api/tests/unit/use_cases/test_stream_helpers.py`
- [X] T007 [P] Add failing HTTP contract tests for default, accepted, and rejected permission modes in `services/api/tests/integration/test_api_conversations.py`
- [X] T008 Add `PermissionMode` validation/default helpers in `services/api/app/domain/value_objects.py`
- [X] T009 Add `permission_mode` to the `Conversation` domain entity in `services/api/app/domain/entities.py`
- [X] T010 Add the Alembic migration for `conversations.permission_mode` with default `request_permissions` in `services/api/alembic/versions/20260617_140216_add_conversation_permission_mode.py`
- [X] T011 Add `permission_mode` to the SQLAlchemy conversation model in `services/api/app/infrastructure/orm_models.py`
- [X] T012 Update conversation persistence mapping for save, get, list, and update paths in `services/api/app/adapters/secondary/persistence/sqlalchemy_conversation_repo.py`
- [X] T013 Update repository contract typing if needed for permission-mode updates in `services/api/app/ports/repositories.py`
- [X] T014 Update request and response schemas for `permission_mode` in `services/api/app/schemas_conversations.py`
- [X] T015 Update conversation fakes and test factories for the new default field in `services/api/tests/conftest.py`
- [X] T016 Add `permission_mode` to `build_pipeline_body` inputs and output in `services/api/app/application/use_cases/_stream_helpers.py`
- [X] T017 Keep stream orchestration thin while resolving and persisting `permission_mode` in `services/api/app/application/use_cases/conversations.py`
- [X] T018 Add optional `permission_mode = 11` to `ChatRequest` in `proto/openclaude.proto`
- [X] T019 Regenerate or document the repository protobuf generation step for `proto/openclaude.proto` in `specs/003-openclaude-v015-ui-audit/quickstart.md`

**Checkpoint**: Foundation ready. API contracts, persistence, and internal runtime contract can now support story work.

---

## Phase 3: User Story 1 - Atualizar runtime com impacto visual conhecido (Priority: P1) MVP

**Goal**: Update the sandbox to OpenClaude v0.15.0 and document which release items require new UI, existing UI validation, or no visual change.

**Independent Test**: Review the release item matrix and patch audit, then build the sandbox image from the pinned v0.15.0 revision.

### Tests for User Story 1

- [X] T020 [P] [US1] Add or update a sandbox bootstrap regression test for the OpenClaude ref in `services/api/tests/adapter/test_docker_bootstrap.py`
- [X] T021 [P] [US1] Create a release-item UI scope checklist with all v0.15.0 items in `specs/003-openclaude-v015-ui-audit/checklists/ui-scope.md`

### Implementation for User Story 1

- [X] T022 [US1] Update the OpenClaude build target to `670744fc70353f2270e86531dffa1c06f4fac79c` in `services/sandbox/Dockerfile`
- [X] T023 [US1] Rebase multimodal protobuf and gRPC patches for v0.15.0 in `services/sandbox/patches/multimodal-proto.patch` and `services/sandbox/patches/multimodal-grpc-handler.patch`
- [X] T024 [US1] Audit MCP integration patch applicability for v0.15.0 in `services/sandbox/patches/mcp-grpc-integration.patch`
- [X] T025 [US1] Audit tool guard and grep/read patch applicability for v0.15.0 in `services/sandbox/patches/grep-tool-n-alias.patch`, `services/sandbox/patches/numeric-parameter-grep-guard.patch`, `services/sandbox/patches/numeric-parameter-grep-wrapper.patch`, `services/sandbox/patches/read-empty-pages.patch`, and `services/sandbox/patches/worktree-tool-guard.patch`
- [X] T026 [US1] Classify `services/sandbox/patches/auto-approve-tools.patch` as retained, changed, removed, or obsolete for v0.15.0 in `specs/003-openclaude-v015-ui-audit/quickstart.md`
- [X] T027 [US1] Refresh the patch series with `services/sandbox/patches/generate_patches.sh` when patch rebases change generated patch contents
- [X] T028 [US1] Build the sandbox image from v0.15.0 and record the result in `specs/003-openclaude-v015-ui-audit/quickstart.md`
- [X] T029 [US1] Mark every release item decision as reviewed in `specs/003-openclaude-v015-ui-audit/checklists/ui-scope.md`
- [X] T030 [US1] Confirm OpenClaude terminal-menu-only agent selection remains out of CappyCloud chat scope in `specs/003-openclaude-v015-ui-audit/spec.md`

**Checkpoint**: User Story 1 is independently testable: the runtime target is pinned, local patches are audited, and UI impact is reviewable.

---

## Phase 4: User Story 2 - Controlar modo de permissoes da sessao (Priority: P2)

**Goal**: Show and persist a per-session permission mode selector in chat, then pass the resolved mode through API, agent pipeline, gRPC, and OpenClaude runtime.

**Independent Test**: Open a conversation, change each mode, send a message, reload, and confirm the selected mode, warning severity, and runtime dispatch all match the active session mode.

### Tests for User Story 2

- [X] T031 [P] [US2] Add stream use-case tests for default, explicit, persisted, and pipeline-dispatched permission modes in `services/api/tests/unit/use_cases/test_conversation_streaming.py`
- [X] T032 [P] [US2] Add integration tests for stream request validation and conversation response `permission_mode` in `services/api/tests/integration/test_api_conversations.py`
- [X] T033 [P] [US2] Add agent runtime tests for permission-mode fallback, gRPC dispatch, and sanitized runtime warning metadata in `services/api/tests/unit/test_agent_permission_mode.py`
- [X] T034 [P] [US2] Add sandbox patch validation notes for all five runtime modes and legacy parameter cleanup in `specs/003-openclaude-v015-ui-audit/quickstart.md`

### Implementation for User Story 2

- [X] T035 [US2] Pass `body.permission_mode` from the HTTP router to the stream use case in `services/api/app/adapters/primary/http/conversations.py`
- [X] T036 [US2] Resolve, validate, and persist the selected session permission mode before dispatch in `services/api/app/application/use_cases/conversations.py`
- [X] T037 [US2] Include the resolved mode in the agent pipeline body in `services/api/app/application/use_cases/_stream_helpers.py`
- [X] T038 [US2] Read and sanitize `permission_mode` from the pipeline body in `services/cappycloud_agent/cappycloud_pipeline.py`
- [X] T039 [US2] Send `permission_mode` on each OpenClaude `ChatRequest` in `services/cappycloud_agent/_grpc_session.py`
- [X] T040 [US2] Add permission-mode fallback and sanitized runtime warning metadata helpers in `services/cappycloud_agent/_grpc_helpers.py`
- [X] T041 [US2] Extend the OpenClaude gRPC handler patch to apply request-scoped permission modes in `services/sandbox/patches/multimodal-grpc-handler.patch`
- [X] T042 [US2] Remove process-wide env-only auto approval by deleting obsolete `services/sandbox/patches/auto-approve-tools.patch` and using request-scoped mode behavior in the gRPC handler patch
- [X] T043 [US2] Remove legacy `OPENCLAUDE_AUTO_APPROVE` defaults/exports and patch regeneration logic from `services/sandbox/env_init.sh` and `services/sandbox/patches/generate_patches.sh`
- [X] T044 [US2] Add the `PermissionMode` type, conversation field, and stream request field in `web/src/api.ts`
- [X] T045 [US2] Add permission-mode options, mode-derived warning metadata, and `runtime_confirmed` state near chat state in `web/src/pages/ChatPage.tsx`
- [X] T046 [US2] Render the permission selector and runtime-confirmed warning indicator before the first message and in the active chat control surface in `web/src/pages/ChatPage.tsx`
- [X] T047 [US2] Add compact selector, caution, and high-risk warning styles in `web/src/components/chat.module.css`
- [X] T048 [US2] Disable mode changes while a stream is active without hiding the current mode in `web/src/pages/ChatPage.tsx`
- [X] T049 [US2] Restore the persisted conversation mode after reload or conversation switch in `web/src/pages/ChatPage.tsx`
- [X] T050 [US2] Verify that new conversations default to `request_permissions` in UI and API flows in `web/src/pages/ChatPage.tsx`

**Checkpoint**: User Story 2 is independently testable: the selector is visible, persists per conversation, sends the selected mode, and shows the correct warning severity.

---

## Phase 5: User Story 3 - Manter o chat estavel apos a atualizacao (Priority: P3)

**Goal**: Preserve existing chat states after the runtime upgrade and selector addition: text, tools, action prompts, diagnostics, model labels, usage, cost, cancellation, and errors.

**Independent Test**: Run controlled chat scenarios for normal answer, tool call, tool error, action-required, payload diagnostics, model/cost display, cancellation, and watcher reload bursts.

### Tests for User Story 3

- [X] T051 [P] [US3] Add regression coverage for tool arguments delivered only by done events in `services/api/tests/unit/use_cases/test_conversation_streaming.py`
- [X] T052 [P] [US3] Add regression coverage for payload diagnostics, model labels, usage, and cost in `services/api/tests/unit/use_cases/test_conversation_payload_diagnostics.py`
- [X] T053 [P] [US3] Add manual validation scenarios for normal answer, tool states, action-required, cancellation, and errors in `specs/003-openclaude-v015-ui-audit/quickstart.md`

### Implementation for User Story 3

- [X] T054 [US3] Preserve existing SSE event parsing while accepting sanitized permission-warning status metadata in `web/src/api.ts`
- [X] T055 [US3] Verify and adjust tool activity, action-required, diagnostics, model, usage, cost, cancel, error, and runtime-confirmed warning rendering around the new selector in `web/src/pages/ChatPage.tsx`
- [X] T056 [US3] Detect and sanitize v0.15.0 startup warning context while preserving tool argument recovery in `services/cappycloud_agent/_grpc_event_handlers.py`
- [X] T057 [US3] Preserve stream event ordering and terminal state behavior after runtime update in `services/cappycloud_agent/_pipeline_event_stream.py`
- [X] T058 [US3] Validate watcher reload burst behavior does not create duplicate or flickering chat/admin states in `specs/003-openclaude-v015-ui-audit/quickstart.md`

**Checkpoint**: User Story 3 is independently testable: existing chat states remain stable after the v0.15.0 update.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final cleanup, documentation, security review, and project gates.

- [X] T059 [P] Update architecture/runtime documentation for the permission-mode stream contract in `docs/ARCHITECTURE.md`
- [X] T060 [P] Update agent runtime context documentation for per-session permission mode and hard safety boundaries in `docs/how-to/agent-runtime-context.md`
- [X] T061 [P] Review frontend copy for sanitized warnings with no secrets, raw logs, hidden prompts, repository contents, or tool inputs in `web/src/pages/ChatPage.tsx`
- [X] T062 Run backend gates `ruff check .`, `ruff format --check .`, `mypy app/`, and `pytest` from `services/api`
- [X] T063 Run frontend gates `npm run lint` and `npm run build` from `web`
- [X] T064 Run the sandbox v0.15.0 build command from `specs/003-openclaude-v015-ui-audit/quickstart.md`
- [X] T065 Run the full quickstart manual scenarios and record any blocked gate or residual risk in `specs/003-openclaude-v015-ui-audit/quickstart.md`
- [X] T066 Check active runtime paths for leftover legacy auto-approval parameters and remove unintended temporary artifacts from `D:\projetos\CappyCloud`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 Setup**: No dependencies.
- **Phase 2 Foundational**: Depends on Phase 1 and blocks all user stories.
- **Phase 3 US1**: Depends on Phase 2; can be delivered as MVP.
- **Phase 4 US2**: Depends on Phase 2; can proceed in parallel with US1 after foundation, but sandbox permission behavior overlaps with patch rebasing.
- **Phase 5 US3**: Depends on Phase 2; should be validated after US1/US2 changes that touch runtime or chat rendering.
- **Phase 6 Polish**: Depends on the selected story scope being complete.

### User Story Dependencies

- **US1 (P1)**: Runtime upgrade and release UI-scope audit. No dependency on US2 or US3.
- **US2 (P2)**: Session permission selector and propagation. Requires foundational schema/proto work; runtime patch changes should be reconciled with US1 patch audit.
- **US3 (P3)**: Regression stability for existing chat states. Best executed after US1 and US2 code paths are present, but tests can be prepared earlier.

### Parallel Opportunities

- Setup tasks T002, T003, and T004 can run in parallel.
- Foundational tests T005, T006, and T007 can run in parallel before implementation.
- US1 test/checklist tasks T020 and T021 can run in parallel.
- US2 tests T031, T032, T033, and T034 can run in parallel.
- US3 tests/checklist tasks T051, T052, and T053 can run in parallel.
- Documentation/security review tasks T059, T060, and T061 can run in parallel after implementation stabilizes.

## Independent Test Criteria

- **US1**: Sandbox builds from OpenClaude `v0.15.0` tag SHA `670744fc70353f2270e86531dffa1c06f4fac79c`; every release item has a reviewed UI decision; every local patch is classified as retained, changed, removed, or obsolete.
- **US2**: New conversations default to `request_permissions`; all five modes can be selected; mode persists per conversation; stream dispatch includes the selected mode; `auto` and `bypass_permissions` show high-risk warning; `accept_edits` shows only lower-severity caution; sanitized runtime warning context can mark the warning as runtime-confirmed; legacy process-wide auto-approval parameters no longer override the selected mode.
- **US3**: Normal answer, tool activity, tool result/error, action-required, payload diagnostics, model label, usage, cost, cancellation, and error rendering remain coherent after the update.

## MVP Scope

1. Complete Phase 1 and Phase 2.
2. Complete Phase 3 (US1).
3. Validate the sandbox build and release-item UI-scope checklist.

US2 is the next product-visible increment and should be implemented before calling the overall feature complete, because it addresses the clarified per-session permission UX.
