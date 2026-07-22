# Tasks: Project-Aware Chat Suggestions

**Input**: Design documents from `specs/009-project-chat-suggestions/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/project-suggestions-api.md, quickstart.md

**Tests**: Include tests because this feature changes backend behavior, database persistence, authorization, scheduled jobs, and frontend UI.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel after dependencies in the same phase are satisfied
- **[Story]**: Maps to US1, US2, or US3 from `spec.md`
- Every task includes concrete CappyCloud file paths

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create the shared structure and contracts that all stories depend on.

- [X] T001 Create SQLAlchemy ORM models for project suggestions and calibration runs in `services/api/app/infrastructure/orm_models_project_suggestions.py`
- [X] T002 Register project suggestion ORM models for metadata discovery in `services/api/app/infrastructure/orm_models.py`
- [X] T003 Create Alembic migration for project suggestion tables and indexes in `services/api/alembic/versions/<timestamp>_add_project_chat_suggestions.py`
- [X] T004 [P] Define domain dataclasses/enums for suggestions, cards, runs, states, sources, and triggers in `services/api/app/domain/project_suggestions.py`
- [X] T005 [P] Define HTTP response/request schemas for project suggestions in `services/api/app/schemas_project_suggestions.py`
- [X] T006 [P] Add frontend TypeScript types for suggestion responses and admin payloads in `web/src/api.ts`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Ports, adapters, fakes, DI, and shared rules that must exist before story work.

**CRITICAL**: No user story work can begin until this phase is complete.

- [X] T007 Define `ProjectSuggestionRepository` port methods in `services/api/app/ports/project_suggestions.py`
- [X] T008 Implement SQLAlchemy project suggestion adapter in `services/api/app/adapters/secondary/persistence/sqlalchemy_project_suggestions.py`
- [ ] T009 Add in-memory project suggestion fake to `services/api/tests/conftest.py`
- [ ] T010 [P] Add adapter contract tests for suggestion save/list/suppress/run behavior in `services/api/tests/adapter/test_project_suggestion_repo.py`
- [X] T011 [P] Add sanitization helpers for suggestion titles, prompts, metadata, and failure reasons in `services/api/app/application/use_cases/project_suggestion_sanitization.py`
- [X] T012 Add repository access checks shared by suggestion use cases in `services/api/app/application/use_cases/project_suggestions.py`
- [X] T013 Wire project suggestion repository and use cases in `services/api/app/adapters/primary/http/deps.py`
- [X] T014 Register the project suggestions router in `services/api/app/main.py`
- [ ] T015 [P] Add baseline unit tests for suggestion sanitization and metadata privacy in `services/api/tests/unit/use_cases/test_project_suggestion_sanitization.py`

**Checkpoint**: Foundation ready - user story implementation can now begin in priority order or in parallel where marked.

---

## Phase 3: User Story 1 - Ver sugestoes especificas do projeto selecionado (Priority: P1) MVP

**Goal**: Users see 3 to 4 useful project-specific cards in the initial chat empty state as soon as a project is selected.

**Independent Test**: Open an empty chat, select project A, confirm cards/copy reflect project A, switch to project B, confirm cards/copy update, click a card, and verify composer state is preserved.

### Tests for User Story 1

- [X] T016 [P] [US1] Add unit tests for initial context suggestion generation from repository metadata, documents, and skills in `services/api/tests/unit/use_cases/test_project_suggestions.py`
- [ ] T017 [P] [US1] Add integration tests for `GET /api/project-suggestions` success, fallback, limit, 403, and 404 cases in `services/api/tests/integration/test_api_project_suggestions.py`
- [ ] T018 [P] [US1] Add frontend API tests or type-safe fixtures for suggestion response mapping in `web/src/api.ts`
- [ ] T019 [P] [US1] Add frontend regression coverage or manual test fixture proving existing conversations with message history do not render initial suggestions in `web/src/pages/ChatPage.tsx`

### Implementation for User Story 1

- [X] T020 [US1] Implement initial suggestion profile loading from repositories, documents, and skills in `services/api/app/adapters/secondary/persistence/sqlalchemy_project_suggestions.py`
- [X] T021 [US1] Implement deterministic initial card generation and safety filtering in `services/api/app/application/use_cases/project_suggestions.py`
- [X] T022 [US1] Implement visible suggestion selection with active/calibrated/initial/fallback states in `services/api/app/application/use_cases/project_suggestions.py`
- [X] T023 [US1] Implement `GET /api/project-suggestions` thin HTTP endpoint in `services/api/app/adapters/primary/http/project_suggestions.py`
- [X] T024 [US1] Add `fetchProjectSuggestions` API client function in `web/src/api.ts`
- [X] T025 [US1] Replace static quick-action card data with loaded project suggestions in `web/src/pages/ChatPage.tsx`
- [ ] T026 [US1] Add empty/loading/error visual states for project suggestion cards in `web/src/pages/ChatPage.tsx`
- [X] T027 [US1] Adjust card layout text fitting and stable dimensions in `web/src/components/chat.module.css`
- [X] T028 [US1] Preserve composer text, attachments, selected sandbox, repository, branch, model, and permission mode when applying a suggestion in `web/src/pages/ChatPage.tsx`

**Checkpoint**: User Story 1 is independently functional as the MVP.

---

## Phase 4: User Story 2 - Aprender com perguntas reais do projeto (Priority: P2)

**Goal**: Daily and document/skill-triggered recalibration improves cards using aggregate anonymized project question patterns.

**Independent Test**: Seed messages for a project, run recalibration, confirm generated suggestions improve active cards without storing or exposing raw prompts, authors, or conversation IDs.

### Tests for User Story 2

- [ ] T029 [P] [US2] Add unit tests for anonymized question pattern extraction and sensitive text rejection in `services/api/tests/unit/use_cases/test_project_suggestion_recalibration.py`
- [ ] T030 [P] [US2] Add unit tests for daily/manual/document/skill trigger behavior and duplicate debounce in `services/api/tests/unit/use_cases/test_project_suggestion_recalibration.py`
- [ ] T031 [P] [US2] Add integration tests for recalibration run persistence and suggestion replacement in `services/api/tests/integration/test_api_project_suggestions.py`

### Implementation for User Story 2

- [X] T032 [US2] Add aggregate authorized-question history queries to `services/api/app/adapters/secondary/persistence/sqlalchemy_project_suggestions.py`
- [X] T033 [US2] Implement project question pattern extraction without raw prompt retention in `services/api/app/application/use_cases/project_suggestion_recalibration.py`
- [ ] T034 [US2] Implement diversity, freshness, frequency, and safety ranking for recalibrated suggestions in `services/api/app/application/use_cases/project_suggestion_recalibration.py`
- [X] T035 [US2] Implement calibration run creation, running, succeeded, failed, and skipped transitions in `services/api/app/application/use_cases/project_suggestion_recalibration.py`
- [X] T036 [US2] Implement daily APScheduler registration for project suggestion recalibration in `services/api/app/infrastructure/project_suggestion_scheduler.py`
- [X] T037 [US2] Wire the daily scheduler into API startup in `services/api/app/main.py`
- [X] T038 [US2] Invoke a scheduling use case after skill create/update/delete from `services/api/app/adapters/primary/http/skills.py` without placing debounce or recalibration rules in the router
- [ ] T039 [US2] Invoke a scheduling use case after document ingest/reindex status changes from `services/api/app/infrastructure/document_ingester.py` without placing debounce or recalibration rules in the ingester
- [X] T040 [US2] Ensure `GET /api/project-suggestions` prefers calibrated active suggestions over initial suggestions in `services/api/app/application/use_cases/project_suggestions.py`

**Checkpoint**: User Stories 1 and 2 both work independently; cards exist immediately and improve over time.

---

## Phase 5: User Story 3 - Controlar qualidade e frescor das sugestoes (Priority: P3)

**Goal**: Administrators can inspect suggestion health, suppress poor suggestions, and trigger recalibration without interrupting normal chat usage.

**Independent Test**: As an admin, inspect suggestion status, suppress a suggestion, verify it disappears from the user endpoint, and trigger recalibration with duplicate-run protection.

### Tests for User Story 3

- [ ] T041 [P] [US3] Add unit tests for admin suppression/reactivation transitions in `services/api/tests/unit/use_cases/test_project_suggestions.py`
- [ ] T042 [P] [US3] Add integration tests for admin status, suppression, manual recalibration, role gates, and duplicate 409 behavior in `services/api/tests/integration/test_api_project_suggestions.py`

### Implementation for User Story 3

- [X] T043 [US3] Implement admin status summary use case in `services/api/app/application/use_cases/project_suggestions.py`
- [X] T044 [US3] Implement suggestion suppression/reactivation use case with sanitized reasons in `services/api/app/application/use_cases/project_suggestions.py`
- [ ] T045 [US3] Implement manual and event-triggered recalibration scheduling use cases with duplicate protection in `services/api/app/application/use_cases/project_suggestion_recalibration.py`
- [X] T046 [US3] Implement `GET /api/project-suggestions/{repository_id}/status` endpoint in `services/api/app/adapters/primary/http/project_suggestions.py`
- [X] T047 [US3] Implement `PATCH /api/project-suggestions/{suggestion_id}` endpoint in `services/api/app/adapters/primary/http/project_suggestions.py`
- [X] T048 [US3] Implement `POST /api/project-suggestions/{repository_id}/recalibrate` endpoint in `services/api/app/adapters/primary/http/project_suggestions.py`
- [X] T049 [US3] Add admin API client functions for suggestion status, suppression, and recalibration in `web/src/api.ts`

**Checkpoint**: All user stories are independently functional.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final validation, accessibility, docs, and quality gates.

- [ ] T050 [P] Add targeted docs for project suggestion behavior and privacy guarantees in `docs/how-to/project-chat-suggestions.md`
- [X] T051 [P] Review and update API error messages for Portuguese clarity in `services/api/app/adapters/primary/http/project_suggestions.py`
- [X] T052 [P] Add frontend smoke coverage or manual QA notes for mobile/desktop empty-state card layout in `specs/009-project-chat-suggestions/quickstart.md`
- [X] T053 [P] Add suggestion load timing smoke validation for the 2-second project-switch target in `specs/009-project-chat-suggestions/quickstart.md`
- [ ] T054 Run backend migration validation with `alembic upgrade head` from `services/api`
- [ ] T055 Run backend gates `ruff check .`, `ruff format --check .`, `mypy app/`, and `pytest` from `services/api`
- [X] T056 Run frontend gates `pnpm lint` and `pnpm build` from `web`
- [ ] T057 Execute the end-to-end validation scenarios from `specs/009-project-chat-suggestions/quickstart.md`
- [X] T058 Document any gate that could not run and the concrete reason in `specs/009-project-chat-suggestions/quickstart.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on Setup and blocks all user stories.
- **US1 (Phase 3)**: Depends on Foundational and is the MVP.
- **US2 (Phase 4)**: Depends on Foundational; should be integrated after US1 for visible replacement behavior, but recalibration use cases can be built independently.
- **US3 (Phase 5)**: Depends on Foundational; status endpoints are more useful after US1/US2 data exists.
- **Polish (Phase 6)**: Depends on all desired stories being complete.

### User Story Dependencies

- **US1**: No dependency on other user stories after foundation.
- **US2**: Can build recalibration after foundation; final user-visible preference over initial cards depends on US1.
- **US3**: Can build admin operations after foundation; meaningful validation depends on suggestions from US1 and runs from US2.

### Parallel Opportunities

- T004, T005, and T006 can run in parallel.
- T010, T011, and T015 can run in parallel after T007-T009 are in place.
- US1 tests T016, T017, T018, and T019 can run in parallel.
- US2 tests T029, T030, and T031 can run in parallel.
- US3 tests T041 and T042 can run in parallel.
- Polish documentation and error-message review tasks T050, T051, and T052 can run in parallel.
- Polish timing validation task T053 can run in parallel with T050, T051, and T052.

---

## Parallel Example: User Story 1

```bash
Task: "Add unit tests for initial context suggestion generation from repository metadata, documents, and skills in services/api/tests/unit/use_cases/test_project_suggestions.py"
Task: "Add integration tests for GET /api/project-suggestions success, fallback, limit, 403, and 404 cases in services/api/tests/integration/test_api_project_suggestions.py"
Task: "Add frontend API tests or type-safe fixtures for suggestion response mapping in web/src/api.ts"
Task: "Add frontend regression coverage or manual test fixture proving existing conversations with message history do not render initial suggestions in web/src/pages/ChatPage.tsx"
```

---

## Parallel Example: User Story 2

```bash
Task: "Add unit tests for anonymized question pattern extraction and sensitive text rejection in services/api/tests/unit/use_cases/test_project_suggestion_recalibration.py"
Task: "Add unit tests for daily/manual/document/skill trigger behavior and duplicate debounce in services/api/tests/unit/use_cases/test_project_suggestion_recalibration.py"
Task: "Add integration tests for recalibration run persistence and suggestion replacement in services/api/tests/integration/test_api_project_suggestions.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 and Phase 2.
2. Complete Phase 3.
3. Validate `GET /api/project-suggestions` and the chat empty-state flow.
4. Stop for demo if needed: users already get useful project-aware cards without history.

### Incremental Delivery

1. Deliver US1 to replace static cards with project-context cards.
2. Add US2 so cards improve from aggregate anonymized question history and document/skill changes.
3. Add US3 so administrators can inspect status, suppress bad cards, and trigger recalibration.
4. Finish Polish gates and quickstart validation.

### Notes

- Keep every backend business rule in `services/api/app/application/use_cases/`.
- Keep HTTP adapters thin and free of direct SQL.
- Do not add sandbox, worktree, Git, OpenRouter, or external documentation calls for MVP suggestion display.
- Verify tests fail before implementation where practical.
- Do not store raw prompts, authors, conversation IDs, secrets, or private snippets in suggestion metadata.
