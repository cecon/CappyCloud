# Tasks: OpenClaude Current Upgrade UI Readiness

**Input**: Design documents from `specs/008-openclaude-current-upgrade/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/runtime-ui-contract.md](contracts/runtime-ui-contract.md), [quickstart.md](quickstart.md)

**Tests**: Include tests for code changes. Backend/runtime changes must include relevant `ruff`, `mypy`, and `pytest` coverage. Frontend changes must include frontend test tooling plus `web/` lint/build validation.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **API**: `services/api/app/`, `services/api/tests/`
- **Use cases**: `services/api/app/application/use_cases/`
- **Ports**: `services/api/app/ports/`
- **HTTP adapters**: `services/api/app/adapters/primary/http/`
- **Secondary adapters**: `services/api/app/adapters/secondary/`
- **Agent runtime**: `services/cappycloud_agent/`
- **Sandbox**: `services/sandbox/`
- **Frontend**: `web/src/`
- **Docs**: `docs/`

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish version evidence, local baseline, frontend test capability, and feature scaffolding before touching runtime or UI.

- [X] T001 Verify OpenClaude v0.27.0 tag and npm latest evidence in `specs/008-openclaude-current-upgrade/research.md`
- [X] T002 Re-check local Dockerfile and production-observed baseline mismatch in `specs/008-openclaude-current-upgrade/research.md`
- [X] T003 [P] Add frontend test tooling and `pnpm test` script in `web/package.json` and `web/vitest.config.ts`
- [X] T004 [P] Create OpenClaude 0.27.0 rollout documentation shell in `docs/how-to/openclaude-v027-rollout.md`
- [X] T005 [P] Create runtime UI validation notes shell in `specs/008-openclaude-current-upgrade/validation-notes.md`
- [X] T006 [P] Inventory current sandbox patches and inline Dockerfile mutations in `specs/008-openclaude-current-upgrade/patch-audit.md`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core runtime contracts and shared types that MUST be complete before user-story implementation.

**CRITICAL**: No user story work can begin until this phase is complete.

- [X] T007 Update OpenClaude target pin to v0.27.0 commit in `services/sandbox/Dockerfile`
- [X] T008 Rebase or replace `grep-tool-n-alias.patch` compatibility against OpenClaude 0.27.0 in `services/sandbox/patches/grep-tool-n-alias.patch`
- [X] T009 Rebase or replace `multimodal-proto.patch` compatibility against OpenClaude 0.27.0 in `services/sandbox/patches/multimodal-proto.patch`
- [X] T010 Rebase or replace `multimodal-grpc-handler.patch` compatibility against OpenClaude 0.27.0 in `services/sandbox/patches/multimodal-grpc-handler.patch`
- [X] T011 Rebase or replace `read-empty-pages.patch` compatibility against OpenClaude 0.27.0 in `services/sandbox/patches/read-empty-pages.patch`
- [X] T012 Preserve CappyCloud permission mode and worktree guard inline mutations for OpenClaude 0.27.0 in `services/sandbox/Dockerfile`
- [X] T013 Preserve request_id, attachment, UTF-8, Portuguese permission response, and CappyCloud-history-only behavior for OpenClaude 0.27.0 in `services/sandbox/Dockerfile`
- [X] T014 [P] Add or update runtime event typing for context indicators and subagent groups in `web/src/api.ts`
- [X] T015 [P] Add or update backend stream schema for context indicators and subagent groups in `services/api/app/schemas_conversations.py`
- [X] T016 [P] Add runtime event normalization tests for new OpenClaude 0.27.0 events in `services/api/tests/unit/test_agent_runtime_regressions.py`
- [X] T017 [P] Add frontend API parsing tests for context and subagent stream events in `web/src/api.test.ts`

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel.

---

## Phase 3: User Story 1 - Mapear Impacto De Interface Do Upgrade (Priority: P1) MVP

**Goal**: Complete the release-delta inventory and make every OpenClaude 0.25.0-0.27.0 theme traceable to a CappyCloud UI decision.

**Independent Test**: Review the matrix and confirm every relevant release theme has a decision: adapt UI, validate existing UI, runtime/operation only, or outside CappyCloud scope.

### Tests for User Story 1

- [X] T018 [P] [US1] Add release-impact completeness test for OpenClaude 0.25.0-0.27.0 themes in `services/api/tests/unit/test_openclaude_upgrade_readiness.py`
- [X] T019 [P] [US1] Add documentation consistency check for target version and baseline in `services/api/tests/unit/test_openclaude_upgrade_readiness.py`

### Implementation for User Story 1

- [X] T020 [US1] Create release impact matrix with evidence links and UI decisions in `specs/008-openclaude-current-upgrade/release-impact-matrix.md`
- [X] T021 [US1] Record local Dockerfile versus production 0.24.0 baseline mismatch and resolution path in `specs/008-openclaude-current-upgrade/patch-audit.md`
- [X] T022 [US1] Document retained, changed, removed, and obsolete OpenClaude patches in `specs/008-openclaude-current-upgrade/patch-audit.md`
- [X] T023 [US1] Update CappyCloud runtime architecture notes for OpenClaude 0.27.0 target and local-only scope in `docs/ARCHITECTURE.md`
- [X] T024 [US1] Update runtime context guidance for frozen OpenClaude 0.27.0 target and CappyCloud source-of-truth rules in `docs/how-to/agent-runtime-context.md`

**Checkpoint**: US1 is independently testable by reviewing `release-impact-matrix.md`, `patch-audit.md`, and evidence consistency tests.

---

## Phase 4: User Story 2 - Preservar O Chat Como Fonte Visual De Verdade (Priority: P1)

**Goal**: Preserve coherent chat timeline, long-running tool activity, subagent grouping, permission timeout handling, context progress, usage and cost.

**Independent Test**: Execute normal, long-running, failed-tool, subagent, permission-timeout, canceled, and resumed-turn scenarios; the chat timeline remains clear, sanitized, and consistent.

### Tests for User Story 2

- [X] T025 [P] [US2] Add backend tests for long-running tool, permission-timeout, stalled, canceled, failed, done, and subagent-group normalization in `services/api/tests/unit/test_agent_runtime_regressions.py`
- [X] T026 [P] [US2] Add conversation streaming tests for context indicator and subagent grouped events in `services/api/tests/unit/use_cases/test_conversation_streaming.py`
- [X] T027 [P] [US2] Add frontend rendering tests for context indicator and grouped subagent activity in `web/src/components/chat/AgentActivityCard.test.tsx`
- [X] T028 [P] [US2] Add frontend timeline regression tests for tool error, permission timeout, cancellation, and final cost display in `web/src/components/MessageTimeline.test.tsx`

### Implementation for User Story 2

- [X] T029 [US2] Normalize OpenClaude 0.27.0 long-running tool and permission-timeout events in `services/cappycloud_agent/_grpc_event_handlers.py`
- [X] T030 [US2] Normalize OpenClaude 0.27.0 subagent or auxiliary-session events into grouped parent-turn payloads in `services/cappycloud_agent/_grpc_event_handlers.py`
- [X] T031 [US2] Preserve sanitized provider/tool/runtime error text for new OpenClaude 0.27.0 failure shapes in `services/cappycloud_agent/_grpc_helpers.py`
- [X] T032 [US2] Propagate context-progress and subagent-group stream events through conversation use cases in `services/api/app/application/use_cases/conversations.py`
- [X] T033 [US2] Propagate context-progress and subagent-group stream events through HTTP streaming adapter in `services/api/app/adapters/primary/http/conversations.py`
- [X] T034 [US2] Parse context-progress, permission-timeout, stalled, canceled, and subagent-group SSE events in `web/src/api.ts`
- [X] T035 [US2] Render the discrete execution-time context indicator in `web/src/components/chat/ChatContextBar.tsx`
- [X] T036 [US2] Render grouped collapsible subagent activity inside parent turns in `web/src/components/chat/AgentActivityCard.tsx`
- [X] T037 [US2] Preserve timeline source-of-truth ordering and final usage/cost display in `web/src/components/MessageTimeline.tsx`
- [X] T038 [US2] Add Portuguese labels for active work, stalled work, permission timeout, canceled work, failed work, subagent group, and context processing in `web/src/components/chat/AgentActivityCard.tsx`
- [X] T039 [US2] Ensure chat page state handles conversation switch during streaming without leaking subagent/context state across conversations in `web/src/pages/ChatPage.tsx`
- [X] T040 [US2] Record timing and state-consistency evidence for long-running, timeout, cancellation, resumed, and failed-turn scenarios in `specs/008-openclaude-current-upgrade/validation-notes.md`

**Checkpoint**: US2 is independently testable through backend stream tests, frontend rendering tests, and quickstart scenarios 1-3.

---

## Phase 5: User Story 3 - Adaptar Catalogo, Providers E Autenticacao Visivel (Priority: P2)

**Goal**: Keep provider onboarding/OAuth state administrator-only while preserving user model/catalog authorization and clear admin provider status.

**Independent Test**: Regular users see only catalog-governed availability; administrators see sanitized provider auth/configuration states and next actions.

### Tests for User Story 3

- [X] T041 [P] [US3] Add unit tests for provider auth state derivation in `services/api/tests/unit/use_cases/test_admin_ai_provider_auth.py`
- [X] T042 [P] [US3] Add backend tests for administrator-only provider auth state exposure in `services/api/tests/integration/test_api_admin_ai_catalog.py`
- [X] T043 [P] [US3] Add backend tests preventing regular-user provider auth state exposure in `services/api/tests/integration/test_api_conversations.py`
- [X] T044 [P] [US3] Add frontend admin provider state tests in `web/src/pages/AdminProvidersPage.test.tsx`
- [X] T045 [P] [US3] Add frontend model picker authorization tests for unavailable and unauthorized models in `web/src/components/ModelPicker.test.tsx`

### Implementation for User Story 3

- [X] T046 [US3] Create provider auth state use case in `services/api/app/application/use_cases/admin_ai_provider_auth.py`
- [X] T047 [US3] Add provider auth response DTO fields without provider-specific decisions in `services/api/app/adapters/primary/http/admin_ai_catalog_helpers.py`
- [X] T048 [US3] Call provider auth state use case from thin admin provider router in `services/api/app/adapters/primary/http/admin_ai_catalog.py`
- [X] T049 [US3] Keep regular-user model/provider responses free of onboarding/OAuth state in `services/api/app/adapters/primary/http/ai_models.py`
- [X] T050 [US3] Add frontend API types for administrator-only provider auth states in `web/src/api.ts`
- [X] T051 [US3] Render provider auth states and next actions for administrators in `web/src/pages/AdminProvidersPage.tsx`
- [X] T052 [US3] Render model unavailable, unauthorized, retired, auth-required, unknown-pricing, and no-authorized-model states in `web/src/components/ModelPicker.tsx`
- [X] T053 [US3] Ensure provider auth and model availability labels use Portuguese user-facing copy in `web/src/pages/AdminProvidersPage.tsx`

**Checkpoint**: US3 is independently testable through use-case tests, admin/provider API tests, model picker tests, and quickstart scenario 4.

---

## Phase 6: User Story 4 - Decidir O Que Nao Vira UI Do Produto (Priority: P3)

**Goal**: Keep upstream branding, buddy companions, and terminal-only features out of the CappyCloud UI unless explicitly mapped to a CappyCloud-native outcome.

**Independent Test**: Review authenticated UI and documentation; terminal-only/upstream-branding features are explicitly out of scope or mapped to product-native states.

### Tests for User Story 4

- [X] T054 [P] [US4] Add UI copy regression test preventing upstream OpenClaude branding from appearing in authenticated surfaces in `web/src/components/layout/BrandMark.test.tsx`
- [X] T055 [P] [US4] Add route/menu regression test preventing terminal-only OpenClaude features from appearing as user menu entries in `web/src/components/layout/routeCoverage.test.ts`

### Implementation for User Story 4

- [X] T056 [US4] Document out-of-scope OpenClaude branding, buddy, and terminal-only features in `specs/008-openclaude-current-upgrade/release-impact-matrix.md`
- [X] T057 [US4] Verify CappyCloud brand mark remains authoritative in authenticated layout in `web/src/components/layout/BrandMark.tsx`
- [X] T058 [US4] Verify user menu does not expose OpenClaude buddy or terminal-only commands in `web/src/components/layout/navigation.ts`
- [X] T059 [US4] Add quickstart evidence for terminal-only and branding exclusion in `specs/008-openclaude-current-upgrade/validation-notes.md`

**Checkpoint**: US4 is independently testable through UI copy/menu tests and quickstart scenario 5.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Local validation, runbook delivery, documentation cleanup, and quality gates across all stories.

- [X] T060 [P] Update local validation guide with final command results and screenshots/notes references in `specs/008-openclaude-current-upgrade/validation-notes.md`
- [X] T061 Create production rollout/rollback runbook with prerequisites, steps, validation checks, rollback triggers, and rollback steps in `docs/how-to/openclaude-v027-rollout.md`
- [X] T062 [P] Update quickstart if implementation changes validation commands or expected outcomes in `specs/008-openclaude-current-upgrade/quickstart.md`
- [X] T063 Build local sandbox image tagged `cappycloud-sandbox-openclaude-v0270-check` from `services/sandbox/Dockerfile`
- [X] T064 Verify built sandbox container reports OpenClaude 0.27.0 from `/openclaude` and record output in `specs/008-openclaude-current-upgrade/validation-notes.md`
- [ ] T065 Run local stack validation with `docker compose up -d --build` and record results in `specs/008-openclaude-current-upgrade/validation-notes.md`
- [X] T066 Run API quality gates `ruff check .`, `ruff format --check .`, `mypy app/`, and `pytest` from `services/api/`
- [X] T067 Run frontend quality gates `pnpm install`, `pnpm test`, `pnpm lint`, and `pnpm build` from `web/`
- [ ] T068 Run quickstart scenarios 1-5 and record pass/fail evidence in `specs/008-openclaude-current-upgrade/validation-notes.md`
- [X] T069 Review generated artifacts for secrets, raw logs, hidden prompts, or production deployment actions in `specs/008-openclaude-current-upgrade/validation-notes.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately.
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories.
- **User Stories (Phase 3+)**: Depend on Foundational completion.
- **Polish (Phase 7)**: Depends on selected user stories being complete.

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational. Provides the MVP evidence baseline.
- **User Story 2 (P1)**: Can start after Foundational. Independent of US1 for implementation, but should use the US1 matrix for review.
- **User Story 3 (P2)**: Can start after Foundational. Independent of US2 except for shared stream/model terminology.
- **User Story 4 (P3)**: Can start after Foundational. Uses the US1 matrix for final documentation.

### Within Each User Story

- Tests should be written before implementation and fail for missing behavior.
- Runtime normalization before API propagation.
- API propagation before frontend parsing.
- Frontend parsing before rendering.
- Rendering before manual quickstart validation.
- Documentation evidence should be updated at each checkpoint.

### Parallel Opportunities

- Setup tasks T003-T006 can run in parallel.
- Foundational tasks T014-T017 can run in parallel with patch compatibility tasks after T007 starts.
- US1 tests T018-T019 can run in parallel.
- US2 tests T025-T028 can run in parallel.
- US3 tests T041-T045 can run in parallel.
- US4 tests T054-T055 can run in parallel.
- US2 and US3 can proceed in parallel after Foundation if separate developers own chat/runtime and admin/model surfaces.

---

## Parallel Example: User Story 2

```text
Task: "Add backend tests for long-running tool, permission-timeout, stalled, canceled, failed, done, and subagent-group normalization in services/api/tests/unit/test_agent_runtime_regressions.py"
Task: "Add conversation streaming tests for context indicator and subagent grouped events in services/api/tests/unit/use_cases/test_conversation_streaming.py"
Task: "Add frontend rendering tests for context indicator and grouped subagent activity in web/src/components/chat/AgentActivityCard.test.tsx"
Task: "Add frontend timeline regression tests for tool error, permission timeout, cancellation, and final cost display in web/src/components/MessageTimeline.test.tsx"
```

---

## Parallel Example: User Story 3

```text
Task: "Add unit tests for provider auth state derivation in services/api/tests/unit/use_cases/test_admin_ai_provider_auth.py"
Task: "Add backend tests for administrator-only provider auth state exposure in services/api/tests/integration/test_api_admin_ai_catalog.py"
Task: "Add backend tests preventing regular-user provider auth state exposure in services/api/tests/integration/test_api_conversations.py"
Task: "Add frontend admin provider state tests in web/src/pages/AdminProvidersPage.test.tsx"
Task: "Add frontend model picker authorization tests for unavailable and unauthorized models in web/src/components/ModelPicker.test.tsx"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup.
2. Complete Phase 2: Foundational runtime pin and shared event contract tasks.
3. Complete Phase 3: User Story 1 release impact matrix and patch audit.
4. Stop and validate: confirm every OpenClaude 0.25.0-0.27.0 theme has a CappyCloud UI decision.

### Incremental Delivery

1. Setup + Foundation -> local OpenClaude 0.27.0 target and shared contracts ready.
2. US1 -> release impact and patch audit ready for review.
3. US2 -> chat timeline, context indicator and subagent activity validated.
4. US3 -> provider/model admin and user visibility validated.
5. US4 -> terminal-only and branding exclusions validated.
6. Polish -> local build, gates, quickstart, and runbook complete.

### Parallel Team Strategy

1. One developer owns sandbox patch compatibility and local build.
2. One developer owns agent/API stream normalization.
3. One developer owns chat frontend states.
4. One developer owns admin/model provider states.
5. Documentation/runbook can proceed after US1 decisions and finish during Polish.

## Notes

- Production deployment is excluded from this feature.
- The runbook is required but must not be executed as part of these tasks.
- Keep OpenClaude target frozen at `0.27.0`.
- Preserve CappyCloud as source of truth for visible conversation state, authorization, usage and cost.
- Avoid committing generated logs, local dumps, screenshots, or large artifacts unless explicitly referenced as intentional documentation.
