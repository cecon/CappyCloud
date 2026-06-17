# Tasks: Agentic Delivery Factory

**Input**: Design documents from `specs/001-agentic-delivery-factory/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/http-api.md](contracts/http-api.md), [quickstart.md](quickstart.md)

**Tests**: Included because the feature changes backend behavior, authorization, persistence, agent runtime context, and frontend workflows.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Prepare shared files, schema registration, and typed API surface.

- [X] T001 Create `services/api/app/domain/agentic_delivery.py` with lifecycle, gate, decision, action, output, metric, source, evidence-link, permission, and sensitive-surface enums from `specs/001-agentic-delivery-factory/data-model.md`
- [X] T002 Create `services/api/app/infrastructure/orm_models_agentic_delivery.py` with ORM table stubs for all entities from `specs/001-agentic-delivery-factory/data-model.md`
- [X] T003 Register `orm_models_agentic_delivery.py` imports in `services/api/app/infrastructure/orm_models.py`
- [X] T004 Create Alembic migration `services/api/alembic/versions/20260616_000001_agentic_delivery_factory.py` for cycle, transition, work package, evidence, output, output-evidence link, gate, decision, knowledge, reuse relationship, agentic delivery permission, authorization, sensitive surface, and metric tables
- [X] T005 Create `services/api/app/ports/agentic_delivery.py` with persistence, retrieval, agentic delivery permission, sensitive surface, external action authorization, and metrics port contracts
- [X] T006 Create `services/api/app/schemas_agentic_delivery.py` with Pydantic request/response models matching `specs/001-agentic-delivery-factory/contracts/http-api.md`
- [X] T007 Add agentic delivery API exports to `web/src/api.ts` matching `specs/001-agentic-delivery-factory/contracts/http-api.md`
- [X] T008 Create `docs/how-to/agentic-delivery-factory.md` with links to `specs/001-agentic-delivery-factory/plan.md`, `data-model.md`, and `quickstart.md`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Implement controls that every user story depends on.

**Critical**: No user story work should start until this phase is complete.

- [X] T009 Implement lifecycle transition validation in `services/api/app/domain/agentic_delivery.py`
- [X] T010 Implement gate completion and final approval validation in `services/api/app/domain/agentic_delivery.py`
- [X] T011 Implement sensitive surface match result value objects and rule validation in `services/api/app/domain/agentic_delivery.py`
- [X] T012 Implement evidence-link validation and unsupported-claim rules in `services/api/app/domain/agentic_delivery.py`
- [X] T013 Implement domain exceptions for invalid transitions, incomplete gates, unauthorized knowledge, denied external actions, invalid sensitive surfaces, and unsupported evidence claims in `services/api/app/domain/agentic_delivery.py`
- [X] T014 Implement `SQLAlchemyAgenticDeliveryRepository` in `services/api/app/adapters/secondary/persistence/sqlalchemy_agentic_delivery_repo.py`
- [X] T015 Implement repository/domain pre-filtered knowledge retrieval in `services/api/app/adapters/secondary/persistence/sqlalchemy_agentic_delivery_repo.py`
- [X] T016 Implement in-memory fake repository for unit and contract tests in `services/api/tests/fakes_agentic_delivery.py`
- [ ] T017 [P] Add parametrized port contract tests for fake and SQLAlchemy adapters in `services/api/tests/adapter/test_agentic_delivery_port_contract.py`
- [ ] T018 [P] Add repository adapter tests for lifecycle, gates, evidence links, knowledge, agentic delivery permissions, sensitive surfaces, authorizations, and metrics persistence in `services/api/tests/adapter/test_sqlalchemy_agentic_delivery_repo.py`
- [X] T019 [P] Add unit tests for lifecycle, gate, evidence-link, and sensitive-surface validation in `services/api/tests/unit/domain/test_agentic_delivery.py`
- [X] T020 Implement platform-admin use cases for granting, listing, disabling, and reactivating `AgenticDeliveryPermission` records and wire dependencies in `services/api/app/adapters/primary/http/deps.py`
- [X] T021 Register the agentic delivery router and admin permission routes in `services/api/app/main.py`
- [X] T022 Add concrete lazy route registration for `/agentic-delivery` in `web/src/App.tsx`

**Checkpoint**: Foundation ready; user story phases can begin.

---

## Phase 3: User Story 1 - Prepare an Agentic Delivery Cycle (Priority: P1) MVP

**Goal**: Users can create a cycle, attach scope/evidence, and prepare a structured work package that reaches `Ready`.

**Independent Test**: Create a cycle with one authorized repository and evidence source, prepare it, and confirm the work package and required gates are returned.

### Tests for User Story 1

- [X] T023 [P] [US1] Add use case tests for creating cycles and rejecting incomplete input in `services/api/tests/unit/use_cases/test_agentic_delivery_prepare.py`
- [X] T024 [P] [US1] Add integration tests for `POST /api/agentic-cycles` and `POST /api/agentic-cycles/{cycle_id}/prepare` in `services/api/tests/integration/test_api_agentic_delivery_prepare.py`
- [ ] T025 [P] [US1] Add frontend API client tests or type assertions for cycle creation payloads in `web/src/api.ts`

### Implementation for User Story 1

- [X] T026 [US1] Implement `CreateAgenticDeliveryCycle` use case in `services/api/app/application/use_cases/agentic_delivery_prepare.py`
- [X] T027 [US1] Implement `PrepareStructuredWorkPackage` use case in `services/api/app/application/use_cases/agentic_delivery_prepare.py`
- [X] T028 [US1] Enforce repository access checks for cycle creation in `services/api/app/application/use_cases/agentic_delivery_prepare.py`
- [X] T029 [US1] Implement evidence source validation and source scope recording in `services/api/app/application/use_cases/agentic_delivery_prepare.py`
- [X] T030 [US1] Implement create and prepare HTTP handlers in `services/api/app/adapters/primary/http/agentic_delivery.py`
- [X] T031 [US1] Add Portuguese validation/error messages for missing goal, scope, outputs, acceptance expectations, and unauthorized repositories in `services/api/app/adapters/primary/http/agentic_delivery.py`
- [X] T032 [US1] Implement cycle creation and work package API functions in `web/src/api.ts`
- [X] T033 [P] [US1] Create cycle creation form component in `web/src/components/agentic-delivery/CycleCreateForm.tsx`
- [X] T034 [P] [US1] Create work package summary component in `web/src/components/agentic-delivery/WorkPackageSummary.tsx`
- [X] T035 [US1] Create `web/src/pages/AgenticDeliveryPage.tsx` with the MVP create-and-prepare workflow
- [X] T036 [US1] Add navigation entry for the workflow in `web/src/components/AppLayout.tsx`

**Checkpoint**: US1 is independently demoable as the MVP.

---

## Phase 4: User Story 2 - Review Agent Outputs With Traceability (Priority: P2)

**Goal**: Reviewers can run a prepared cycle, inspect agent outputs, evidence, gates, decisions, lifecycle transitions, and blocked approvals.

**Independent Test**: Prepare a cycle, start a run, complete or simulate outputs, open the review package, record decisions, and verify approval is blocked until gates are complete.

### Tests for User Story 2

- [X] T037 [P] [US2] Add use case tests for starting a cycle run and rejecting duplicate or invalid runs in `services/api/tests/unit/use_cases/test_agentic_delivery_run.py`
- [X] T038 [P] [US2] Add use case tests for review decisions, gate completion, rework, rejection, and approval blocking in `services/api/tests/unit/use_cases/test_agentic_delivery_review.py`
- [X] T039 [P] [US2] Add integration tests for run, paginated review package, review decisions, and transition endpoints in `services/api/tests/integration/test_api_agentic_delivery_review.py`
- [X] T040 [P] [US2] Add agent context tests for review-only sandbox/worktree changes in `services/api/tests/unit/test_agentic_delivery_agent_context.py`
- [X] T041 [P] [US2] Add evidence-link tests for supported, unsupported, contradicted, and stale claims in `services/api/tests/unit/use_cases/test_agentic_delivery_evidence_links.py`

### Implementation for User Story 2

- [X] T042 [US2] Implement `RunAgenticDeliveryCycle` use case with `AgentTask` linkage in `services/api/app/application/use_cases/agentic_delivery_prepare.py`
- [X] T043 [US2] Implement `GetReviewPackage` use case with cursor/limit handling for outputs, evidence links, and review decisions in `services/api/app/application/use_cases/agentic_delivery_review.py`
- [X] T044 [US2] Implement `RecordReviewDecision` use case in `services/api/app/application/use_cases/agentic_delivery_review.py`
- [X] T045 [US2] Implement `TransitionAgenticDeliveryCycle` use case with controlled lifecycle graph in `services/api/app/application/use_cases/agentic_delivery_review.py`
- [X] T046 [US2] Implement compliance gate auto-triggering from sensitive surface matches in `services/api/app/application/use_cases/agentic_delivery_review.py`
- [X] T047 [US2] Implement agent output to evidence source linking in `services/api/app/application/use_cases/agentic_delivery_review.py`
- [X] T048 [US2] Implement run, review package, review decision, and transition HTTP handlers in `services/api/app/adapters/primary/http/agentic_delivery.py`
- [X] T049 [US2] Extend agent pipeline request body with optional cycle context in `services/api/app/application/use_cases/conversations.py`
- [X] T050 [US2] Render work package, review-only constraints, and evidence expectations in `services/cappycloud_agent/_agent_prompt_sections.py`
- [X] T051 [US2] Propagate cycle metadata through agent context in `services/cappycloud_agent/_agent_context.py`
- [X] T052 [US2] Add run, review package, decision, and transition API functions in `web/src/api.ts`
- [X] T053 [P] [US2] Create review gate panel in `web/src/components/agentic-delivery/ReviewGatePanel.tsx`
- [X] T054 [P] [US2] Create agent output review list with evidence-link status in `web/src/components/agentic-delivery/AgentOutputReviewList.tsx`
- [X] T055 [P] [US2] Create lifecycle status display in `web/src/components/agentic-delivery/CycleLifecycleBadge.tsx`
- [X] T056 [US2] Integrate run and review package workflow into `web/src/pages/AgenticDeliveryPage.tsx`

**Checkpoint**: US1 and US2 both work independently; external actions still require separate authorization.

---

## Phase 5: User Story 3 - Preserve Knowledge Across Cycles (Priority: P3)

**Goal**: Completed cycle knowledge can be reused inside authorized repository/domain scope, and unauthorized cross-domain content is excluded before agent or UI exposure.

**Independent Test**: Seed similar knowledge in two repositories, grant access to only one, search from a cycle, and confirm only authorized knowledge appears.

### Tests for User Story 3

- [X] T057 [P] [US3] Add use case tests for repository/domain-scoped knowledge search and explicit reuse relationships in `services/api/tests/unit/use_cases/test_agentic_delivery_knowledge.py`
- [ ] T058 [P] [US3] Add adapter tests proving unauthorized repositories are filtered before ranking in `services/api/tests/adapter/test_sqlalchemy_agentic_delivery_knowledge.py`
- [X] T059 [P] [US3] Add integration tests for `POST /api/agentic-cycles/knowledge/search` in `services/api/tests/integration/test_api_agentic_delivery_knowledge.py`
- [ ] T060 [P] [US3] Add pagination and limit tests for knowledge search in `services/api/tests/integration/test_api_agentic_delivery_knowledge.py`

### Implementation for User Story 3

- [X] T061 [US3] Implement `SearchReusableKnowledge` use case with repository/domain access checks in `services/api/app/application/use_cases/agentic_delivery_knowledge.py`
- [X] T062 [US3] Implement `CreateKnowledgeReuseRelationship` use case in `services/api/app/application/use_cases/agentic_delivery_knowledge.py`
- [X] T063 [US3] Implement stale or unavailable evidence marking for reusable knowledge in `services/api/app/application/use_cases/agentic_delivery_knowledge.py`
- [X] T064 [US3] Implement cursor or limit pagination for reusable knowledge search in `services/api/app/application/use_cases/agentic_delivery_knowledge.py`
- [X] T065 [US3] Add audit logging for denied knowledge retrieval in `services/api/app/application/use_cases/agentic_delivery_knowledge.py`
- [X] T066 [US3] Implement knowledge search HTTP handler in `services/api/app/adapters/primary/http/agentic_delivery.py`
- [X] T067 [US3] Add reusable knowledge API functions in `web/src/api.ts`
- [X] T068 [P] [US3] Create reusable knowledge search component in `web/src/components/agentic-delivery/ReusableKnowledgeSearch.tsx`
- [X] T069 [US3] Integrate reusable knowledge suggestions into `web/src/pages/AgenticDeliveryPage.tsx`

**Checkpoint**: Knowledge reuse works without violating repository/domain isolation.

---

## Phase 6: Sensitive Surface Configuration

**Goal**: Users with `manage_sensitive_surfaces` permission, or platform admins, can configure the surfaces that deterministically trigger compliance review.

**Independent Test**: Create a sensitive surface, prepare a cycle that matches it, and confirm a compliance gate is required.

### Tests for Sensitive Surface Configuration

- [X] T070 [P] Add use case tests for creating, updating, listing, deactivating, and permission-denying sensitive surfaces in `services/api/tests/unit/use_cases/test_agentic_delivery_sensitive_surfaces.py`
- [ ] T071 [P] Add integration tests for admin permission grants and sensitive surface endpoints, including denied users without `manage_sensitive_surfaces`, in `services/api/tests/integration/test_api_agentic_delivery_sensitive_surfaces.py`

### Implementation for Sensitive Surface Configuration

- [X] T072 Implement `ManageSensitiveSurfaces` use cases in `services/api/app/application/use_cases/agentic_delivery_review.py`
- [X] T073 Enforce active `manage_sensitive_surfaces` `AgenticDeliveryPermission` or platform admin permission for sensitive surface management in `services/api/app/application/use_cases/agentic_delivery_review.py`
- [X] T074 Implement admin permission and sensitive surface list/create/update HTTP handlers in `services/api/app/adapters/primary/http/agentic_delivery.py`
- [X] T075 Add sensitive surface API functions in `web/src/api.ts`
- [X] T076 [P] Create sensitive surface management component in `web/src/components/agentic-delivery/SensitiveSurfaceManager.tsx`
- [X] T077 Integrate sensitive surface indicators into `web/src/pages/AgenticDeliveryPage.tsx`

**Checkpoint**: Compliance triggering is configurable and deterministic.

---

## Phase 7: External Action Authorization

**Goal**: Only explicitly authorized users can authorize actions outside the review context, and permission/gate completion is rechecked at execution time.

**Independent Test**: Attempt external action authorization before approval, after approval as an unauthorized reviewer, and after approval as an authorized user.

### Tests for External Action Authorization

- [X] T078 [P] Add use case tests for active `authorize_external_action` permission and gate rechecks in `services/api/tests/unit/use_cases/test_agentic_delivery_actions.py`
- [X] T079 [P] Add integration tests for `POST /api/agentic-cycles/{cycle_id}/external-actions/authorize` in `services/api/tests/integration/test_api_agentic_delivery_actions.py`

### Implementation for External Action Authorization

- [X] T080 Implement `AuthorizeExternalAction` use case in `services/api/app/application/use_cases/agentic_delivery_actions.py`
- [X] T081 Recheck active `authorize_external_action` `AgenticDeliveryPermission` and completed required gates at execution boundary in `services/api/app/application/use_cases/agentic_delivery_actions.py`
- [X] T082 Add audit logging for denied external action authorization in `services/api/app/application/use_cases/agentic_delivery_actions.py`
- [X] T083 Implement external action authorization HTTP handler in `services/api/app/adapters/primary/http/agentic_delivery.py`
- [X] T084 Add external action authorization API function in `web/src/api.ts`
- [X] T085 [P] Create external action authorization panel in `web/src/components/agentic-delivery/ExternalActionAuthorizationPanel.tsx`
- [X] T086 Integrate external action authorization into `web/src/pages/AgenticDeliveryPage.tsx`

**Checkpoint**: External state changes remain blocked unless authorization succeeds server-side.

---

## Phase 8: User Story 4 - Track Delivery Value and Capacity Impact (Priority: P4)

**Goal**: Managers can inspect cycle metrics for throughput, quality, rework, blockers, evidence coverage, human review load, usage, and cost.

**Independent Test**: Run or seed multiple cycles and verify metrics distinguish approval, rejection, cancellation, failure, rework, evidence coverage, and provider usage availability.

### Tests for User Story 4

- [X] T087 [P] [US4] Add use case tests for cycle metric aggregation in `services/api/tests/unit/use_cases/test_agentic_delivery_metrics.py`
- [X] T088 [P] [US4] Add integration tests for `GET /api/agentic-cycles/{cycle_id}/metrics` in `services/api/tests/integration/test_api_agentic_delivery_metrics.py`
- [ ] T089 [P] [US4] Add performance and MVP-limit tests for metrics, review package, work package, and knowledge retrieval in `services/api/tests/integration/test_api_agentic_delivery_performance.py`

### Implementation for User Story 4

- [X] T090 [US4] Implement `GetCycleMetrics` use case in `services/api/app/application/use_cases/agentic_delivery_metrics.py`
- [X] T091 [US4] Persist metrics for lifecycle transitions, gate outcomes, rework count, evidence coverage, blocker count, duration, and provider usage availability in `services/api/app/application/use_cases/agentic_delivery_metrics.py`
- [X] T092 [US4] Implement pagination and limit handling for metrics responses in `services/api/app/application/use_cases/agentic_delivery_metrics.py`
- [X] T093 [US4] Implement metrics HTTP handler in `services/api/app/adapters/primary/http/agentic_delivery.py`
- [X] T094 [US4] Add metrics API functions in `web/src/api.ts`
- [X] T095 [P] [US4] Create metrics summary component in `web/src/components/agentic-delivery/CycleMetricsSummary.tsx`
- [X] T096 [US4] Integrate metrics summary into `web/src/pages/AgenticDeliveryPage.tsx`

**Checkpoint**: Delivery value can be measured for completed cycles.

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Hardening, documentation, and validation across all stories.

- [X] T097 [P] Update `docs/how-to/agentic-delivery-factory.md` with operational runbook, security invariants, and demo script
- [X] T098 [P] Add frontend loading, empty, error, and denied-permission states in `web/src/pages/AgenticDeliveryPage.tsx`
- [X] T099 [P] Add accessibility labels and keyboard paths for agentic delivery controls in `web/src/components/agentic-delivery/CycleCreateForm.tsx`
- [X] T100 Add final API schema exports and import checks in `services/api/app/schemas.py`
- [ ] T101 Run quickstart validation from `specs/001-agentic-delivery-factory/quickstart.md`
- [X] T102 Run `ruff check .`, `ruff format --check .`, `mypy app/`, and `pytest` from `services/api/`
- [ ] T103 Run `pnpm --dir web lint` and `pnpm --dir web build` from repository root
- [X] T104 Document any validation gate that cannot run in `docs/how-to/agentic-delivery-factory.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 Setup**: no dependencies.
- **Phase 2 Foundational**: depends on Phase 1 and blocks user stories.
- **Phase 3 US1**: depends on Phase 2 and is the MVP.
- **Phase 4 US2**: depends on Phase 2; full value improves after US1.
- **Phase 5 US3**: depends on Phase 2; can use seeded cycles.
- **Phase 6 Sensitive Surfaces**: depends on Phase 2; should complete before compliance-heavy US2 validation.
- **Phase 7 External Actions**: depends on Phase 2 and US2 gate/lifecycle behavior.
- **Phase 8 US4**: depends on Phase 2; can use seeded cycles and metrics.
- **Phase 9 Polish**: depends on the desired story set.

### User Story Dependencies

- **US1 Prepare Cycle**: first MVP increment.
- **US2 Review Outputs**: can start after foundation, but needs US1 for full user flow.
- **US3 Preserve Knowledge**: can start after foundation using seeded data.
- **Sensitive Surface Configuration**: supports compliance triggering required by US2.
- **External Action Authorization**: requires lifecycle/gate completion from US2.
- **US4 Track Metrics**: can start after foundation using seeded cycle data.

### Parallel Opportunities

- T017, T018, and T019 can run in parallel after T009-T016 are sketched.
- T023, T024, and T025 can be written in parallel for US1.
- T033 and T034 can be implemented in parallel for US1.
- T037, T038, T039, T040, and T041 can be written in parallel for US2.
- T053, T054, and T055 can be implemented in parallel for US2.
- T057, T058, T059, and T060 can be written in parallel for US3.
- T070 and T071 can be written in parallel for sensitive surfaces.
- T078 and T079 can be written in parallel for external actions.
- T087, T088, and T089 can be written in parallel for US4.
- T097, T098, and T099 can run in parallel during polish.

## Parallel Example: User Story 1

```text
Task: T023 Add use case tests in services/api/tests/unit/use_cases/test_agentic_delivery_prepare.py
Task: T024 Add integration tests in services/api/tests/integration/test_api_agentic_delivery_prepare.py
Task: T025 Add frontend API client checks in web/src/api.ts
Task: T033 Create CycleCreateForm in web/src/components/agentic-delivery/CycleCreateForm.tsx
Task: T034 Create WorkPackageSummary in web/src/components/agentic-delivery/WorkPackageSummary.tsx
```

## Parallel Example: User Story 2

```text
Task: T037 Add run use case tests in services/api/tests/unit/use_cases/test_agentic_delivery_run.py
Task: T038 Add review use case tests in services/api/tests/unit/use_cases/test_agentic_delivery_review.py
Task: T039 Add review integration tests in services/api/tests/integration/test_api_agentic_delivery_review.py
Task: T040 Add agent context tests in services/api/tests/unit/test_agentic_delivery_agent_context.py
Task: T053 Create ReviewGatePanel in web/src/components/agentic-delivery/ReviewGatePanel.tsx
Task: T054 Create AgentOutputReviewList in web/src/components/agentic-delivery/AgentOutputReviewList.tsx
```

## Implementation Strategy

### MVP First

1. Complete Phase 1 and Phase 2.
2. Complete Phase 3 only.
3. Validate US1 independently with create and prepare endpoints plus UI.
4. Demo the structured work package flow before adding review, knowledge, sensitive surfaces, external actions, or metrics.

### Incremental Delivery

1. Add US1 for cycle preparation.
2. Add US2 for run, review gates, lifecycle, evidence links, and review-only agent outputs.
3. Add US3 for repository/domain-isolated knowledge reuse.
4. Add sensitive surface configuration for deterministic compliance.
5. Add external action authorization.
6. Add US4 for metrics and management visibility.

### Security Invariants

- Knowledge retrieval must pre-filter by repository/domain access before candidate content reaches the agent.
- Compliance gates must be triggered by configured sensitive surfaces, not by reviewer memory.
- Sensitive surface management must require `manage_sensitive_surfaces` permission or platform admin rights.
- External action authorization must recheck active `authorize_external_action` permission and gate completion at execution time.
- Generated changes must remain in sandbox/worktree review context until external authorization succeeds.
