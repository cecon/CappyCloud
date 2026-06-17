# Quickstart: Agentic Delivery Factory Validation

## Prerequisites

- Local CappyCloud stack configured.
- At least one sandbox and one repository registered.
- A user with access to the repository and selected model.
- API dependencies installed in `services/api`.
- Frontend dependencies installed in `web`.

## Backend Setup

```bash
cd services/api
alembic upgrade head
```

## Validation Scenario 1: Prepare an Agentic Delivery Cycle

1. Create a cycle through `POST /api/agentic-cycles` with one authorized repository, business goal, scope, expected outputs, acceptance expectations, and evidence sources.
2. Call `POST /api/agentic-cycles/{cycle_id}/prepare`.
3. Verify the cycle reaches `Ready`.
4. Verify the work package lists scope, outputs, review criteria, evidence sources, and required gates.

Expected result: the user receives a review-ready work package without manual reformatting.

## Validation Scenario 2: Review Agent Outputs and Gate Enforcement

1. Start execution with `POST /api/agentic-cycles/{cycle_id}/run`.
2. Simulate or complete agent output generation.
3. Open `GET /api/agentic-cycles/{cycle_id}/review`.
4. Try to transition to `Approved` before gates are complete.
5. Approve product, architecture, and quality gates.
6. If a sensitive surface is detected, approve compliance too.
7. Transition to `Approved`.

Expected result: approval is blocked until required gates are complete.

## Validation Scenario 2a: Run Endpoint

1. Prepare a cycle until it reaches `Ready`.
2. Call `POST /api/agentic-cycles/{cycle_id}/run`.
3. Confirm the response includes an `agent_task_id` and the cycle moves to `Running`.
4. Call the endpoint again while the cycle is running.

Expected result: the first call starts a single agent run, and the second call is rejected with a conflict.

## Validation Scenario 3: Knowledge Isolation

1. Create reusable knowledge for repository A and repository B.
2. Grant the user access only to repository A.
3. Search reusable knowledge from a cycle scoped to repository A.
4. Confirm repository B knowledge is not returned even when semantically similar.

Expected result: unauthorized repository/domain knowledge is excluded before it reaches the agent or UI.

## Validation Scenario 4: External Action Authorization

1. Complete all required gates and approve the cycle.
2. Attempt external action authorization as a user without explicit repository/domain permission.
3. Attempt again as an authorized user.

Expected result: the unauthorized attempt is denied and recorded; the authorized attempt succeeds only after gate completion is rechecked.

## Validation Scenario 5: Metrics

1. Complete at least one cycle with agent outputs and review decisions.
2. Request `GET /api/agentic-cycles/{cycle_id}/metrics`.
3. Confirm duration, rework count, gate outcomes, evidence coverage, and provider usage/cost availability are represented.

Expected result: cycle metrics distinguish approval, rejection, cancellation, and failure outcomes.

## Validation Scenario 6: Sensitive Surface Configuration

1. Create or update a sensitive surface for an authorized repository/domain.
2. Prepare a cycle whose scope or generated changes match the surface rules.
3. Confirm compliance is automatically added as a required gate.

Expected result: compliance triggering does not depend on reviewer memory.

## Validation Scenario 7: Performance And Limits

1. Create a cycle with representative data near MVP limits: 100 evidence sources, 50 outputs, 20 review decisions, and 1,000 reusable knowledge items in the repository/domain.
2. Measure create/prepare, review package, knowledge search, and metrics calls.

Expected result: work package creation completes under 5 seconds, review package and metrics under 3 seconds, and authorized knowledge search under 2 seconds.

## Required Gates

```bash
cd services/api
ruff check .
ruff format --check .
mypy app/
pytest
```

```bash
pnpm --dir web lint
pnpm --dir web build
```

If a gate cannot run locally, record the exact missing dependency or environment condition in the implementation notes.
