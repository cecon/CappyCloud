# Tasks: Persistent User Workspaces

**Input**: Design documents from `specs/006-persistent-user-workspaces/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Include tests for API use cases, persistence behavior, sandbox sidecar contracts, and Docker smoke validation. Frontend checks apply only if status copy/UI is touched during implementation.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Prepare the feature surface and test scaffolding.

- [X] T001 Review existing conversation workspace creation in `services/api/app/application/use_cases/_conversation_crud.py`, `services/cappycloud_agent/_environment_manager.py`, and `services/sandbox/session_server.js`
- [X] T002 [P] Add shared workspace status constants or value-object validation in `services/api/app/domain/value_objects.py`
- [X] T003 [P] Add user workspace fake repository scaffold in `services/api/tests/conftest.py`
- [X] T004 [P] Add sandbox user workspace fake/client fixture scaffold in `services/api/tests/conftest.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core persistence, ports, and contracts that all stories need.

**CRITICAL**: No user story work can begin until this phase is complete.

- [X] T005 Create `UserRepositoryWorkspace` domain entity in `services/api/app/domain/entities.py`
- [X] T006 Create Alembic migration for `user_repository_workspaces` in `services/api/alembic/versions/`
- [X] T007 Add `UserRepositoryWorkspace` ORM model and metadata import in `services/api/app/infrastructure/orm_models_user_workspaces.py` and `services/api/app/infrastructure/orm_models.py`
- [X] T008 [P] Define `UserRepositoryWorkspaceRepository` port in `services/api/app/ports/user_workspaces.py`
- [X] T009 [P] Define sandbox workspace gateway port in `services/api/app/ports/sandbox_workspaces.py`
- [X] T010 Implement SQLAlchemy repository adapter in `services/api/app/adapters/secondary/persistence/sqlalchemy_user_workspace_repo.py`
- [X] T011 Implement sandbox workspace HTTP adapter in `services/api/app/adapters/secondary/sandbox_user_workspace_client.py`
- [X] T012 Wire new repositories/gateways in `services/api/app/adapters/primary/http/deps.py`
- [X] T013 [P] Add repository contract tests for user workspace persistence in `services/api/tests/adapter/test_user_workspace_repo.py`
- [X] T014 [P] Add sandbox gateway contract tests in `services/api/tests/adapter/test_sandbox_user_workspace_gateway.py`

**Checkpoint**: Foundation ready - user story implementation can now begin.

---

## Phase 3: User Story 1 - Reuse My Prepared Repository Workspace (Priority: P1) MVP

**Goal**: Reuse a prepared baseline workspace for repeat conversations by the same user/repository/base branch.

**Independent Test**: Start two conversations for the same user/repository/base branch and verify the second one reuses the same user workspace record/path instead of full preparation.

### Tests for User Story 1

- [X] T015 [P] [US1] Add unit tests for ensure/reuse behavior in `services/api/tests/unit/use_cases/test_user_workspaces.py`
- [X] T016 [P] [US1] Add integration test for authenticated ensure endpoint in `services/api/tests/integration/test_user_workspaces_api.py`
- [X] T017 [P] [US1] Add sandbox sidecar test for idempotent user workspace ensure in `services/api/tests/integration/test_sandbox_user_workspaces.py`

### Implementation for User Story 1

- [X] T018 [US1] Implement `EnsureUserRepositoryWorkspace` use case in `services/api/app/application/use_cases/user_workspaces.py`
- [X] T019 [US1] Add schemas for user workspace ensure/status in `services/api/app/schemas_user_workspaces.py`
- [X] T020 [US1] Add thin HTTP routes for ensure/list in `services/api/app/adapters/primary/http/user_workspaces.py`
- [X] T021 [US1] Register user workspace router in `services/api/app/main.py`
- [X] T022 [US1] Add `/user-workspaces/ensure` handler in `services/sandbox/session_server.js`
- [X] T023 [US1] Add safe user workspace path validation helpers in `services/sandbox/session_server.js`
- [X] T024 [US1] Extend conversation repo enrichment to include source user workspace metadata in `services/api/app/application/use_cases/_stream_helpers.py`
- [X] T025 [US1] Update `EnvironmentManager` to ensure/reuse user workspace before conversation session creation in `services/cappycloud_agent/_environment_manager.py`
- [X] T026 [US1] Emit distinct reuse/create/repair status messages through agent events in `services/cappycloud_agent/_task_launcher.py`

**Checkpoint**: User Story 1 independently verifies repeat conversations reuse a user baseline.

---

## Phase 4: User Story 2 - Keep Editing Sessions Isolated (Priority: P2)

**Goal**: Preserve mutation isolation by deriving mutating conversation workspaces from the user's baseline rather than mutating the baseline.

**Independent Test**: Run two conversations for the same user/repository; mutate files in one and verify the other and the user baseline remain clean.

### Tests for User Story 2

- [X] T027 [P] [US2] Add unit tests for mutating flow workspace selection in `services/api/tests/unit/use_cases/test_conversation_workspace_isolation.py`
- [X] T028 [P] [US2] Add sandbox test proving dirty baseline is repaired before reuse in `services/api/tests/integration/test_sandbox_user_workspaces.py`
- [X] T029 [P] [US2] Add integration test for parallel conversations not sharing dirty changes in `services/api/tests/integration/test_sandbox_user_workspaces.py`

### Implementation for User Story 2

- [X] T030 [US2] Extend session payload contract to include `source_workspace_path` in `services/cappycloud_agent/_environment_manager.py`
- [X] T031 [US2] Update `services/sandbox/session_server.js` to derive conversation worktrees from a clean user workspace when provided
- [X] T032 [US2] Update `services/sandbox/session_start.sh` to support safe source workspace derivation without mutating the source baseline
- [X] T033 [US2] Update worktree validation so agent working directories remain conversation-scoped in `services/cappycloud_agent/_worktree_validation.py`
- [X] T034 [US2] Add dirty-state detection and status transition handling in `services/api/app/application/use_cases/user_workspaces.py`

**Checkpoint**: User Stories 1 and 2 both work independently and preserve isolation.

---

## Phase 5: User Story 3 - Recover and Reuse Safely (Priority: P3)

**Goal**: Repair missing/unhealthy user workspaces and clean stale baselines safely.

**Independent Test**: Delete a recorded user workspace path and verify the next conversation repairs it automatically.

### Tests for User Story 3

- [X] T035 [P] [US3] Add unit tests for missing/repairing/error transitions in `services/api/tests/unit/use_cases/test_user_workspaces.py`
- [X] T036 [P] [US3] Add integration test for automatic repair after deleted workspace path in `services/api/tests/integration/test_user_workspaces_api.py`

### Implementation for User Story 3

- [X] T037 [US3] Implement workspace health-check and repair flow in `services/api/app/application/use_cases/user_workspaces.py`
- [X] T038 [US3] Add sandbox health/status response for user workspaces in `services/sandbox/session_server.js`
- [X] T039 [US3] Add cleanup use case for stale user workspaces in `services/api/app/application/use_cases/user_workspaces.py`
- [X] T040 [US3] Add owner/admin cleanup route in `services/api/app/adapters/primary/http/user_workspaces.py`
- [X] T041 [US3] Ensure cleanup never deletes active conversation workspaces in `services/sandbox/session_server.js`

**Checkpoint**: All user stories are independently functional.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, UX clarity, and final verification.

- [X] T042 [P] Update runtime documentation in `docs/how-to/agent-runtime-context.md`
- [X] T043 [P] Update sandbox/worktree architecture notes in `docs/decisions/adr-002-sandbox-runtime-and-worktree-sessions.md`
- [ ] T044 [P] Add optional frontend status copy for reused/repaired workspace states in `web/src/pages/ChatPage.tsx`
- [X] T045 Run `docker compose run --rm --no-deps -v "D:/projetos/CappyCloud/services/api:/app" api python -m compileall -q app`
- [X] T046 Run backend gates `ruff check .`, `ruff format --check .`, `mypy app/`, and `pytest` from `services/api/`, or document unavailable dev tooling
- [ ] T047 Run `npm --prefix web run lint -- --max-warnings=0` and frontend build if `web/` changed
- [ ] T048 Run Docker smoke validation from `specs/006-persistent-user-workspaces/quickstart.md`
- [X] T049 Review security boundaries for cross-user filesystem leakage and dirty baseline reuse

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on Setup and blocks all user stories.
- **User Story 1 (Phase 3)**: Depends on Foundational and is the MVP.
- **User Story 2 (Phase 4)**: Depends on Foundational; should be validated after or alongside US1 because it protects the reuse behavior.
- **User Story 3 (Phase 5)**: Depends on Foundational and can follow US1.
- **Polish (Phase 6)**: Depends on selected user stories being complete.

### User Story Dependencies

- **US1**: Independent MVP after foundation.
- **US2**: Builds on the same workspace registry but has independent isolation tests.
- **US3**: Builds on workspace registry and sandbox health contracts.

### Parallel Opportunities

- T002-T004 can run in parallel.
- T008-T009 and T013-T014 can run in parallel after entity/migration decisions.
- US1 tests T015-T017 can run in parallel before implementation.
- US2 tests T027-T029 can run in parallel.
- US3 tests T035-T036 can run in parallel.
- Documentation tasks T042-T043 can run in parallel with final verification.

---

## Parallel Example: User Story 1

```text
Task: "Add unit tests for ensure/reuse behavior in services/api/tests/unit/use_cases/test_user_workspaces.py"
Task: "Add integration test for authenticated ensure endpoint in services/api/tests/integration/test_user_workspaces_api.py"
Task: "Add sandbox sidecar test for idempotent user workspace ensure in services/api/tests/integration/test_sandbox_user_workspaces.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 setup.
2. Complete Phase 2 foundation.
3. Complete Phase 3 user workspace ensure/reuse.
4. Validate repeat conversation reuse without enabling baseline mutation.

### Incremental Delivery

1. Deliver US1 to reduce repeated setup.
2. Deliver US2 to harden mutation isolation before broad rollout.
3. Deliver US3 to repair and clean stale workspaces.
4. Finish docs, optional UI copy, and full gate verification.
