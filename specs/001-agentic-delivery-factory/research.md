# Research: Agentic Delivery Factory

## Decision: Add a dedicated agentic delivery feature slice

**Rationale**: The workflow has its own lifecycle, gates, outputs, authorizations, and metrics. Keeping it separate from generic conversations avoids overloading chat state while still linking cycles to conversations and repositories.

**Alternatives considered**:
- Store cycle state inside `Conversation.repos` JSON only. Rejected because lifecycle, gates, authorization, and metrics need queryable, auditable records.
- Treat every cycle as only an agent task. Rejected because `AgentTask` tracks execution, not product review, compliance, knowledge reuse, or external action authorization.

## Decision: Enforce repository/domain isolation during knowledge retrieval

**Rationale**: The spec requires knowledge isolation before content reaches the agent. The existing `skills.repository_id` and user repository access model provide the right anchor for pre-filtering knowledge by repository/domain.

**Alternatives considered**:
- Prompt the agent to ignore other repositories. Rejected because prompt guidance is not access control.
- Retrieve globally and filter after ranking. Rejected because unauthorized candidates would already have crossed the retrieval boundary.

## Decision: Model lifecycle states as a closed transition graph

**Rationale**: Draft, Ready, Running, Review, Rework, Approved, Rejected, Cancelled, and Failed represent distinct audit and metric outcomes. Controlled transitions prevent approval without review and make rejection, cancellation, and failure measurable.

**Alternatives considered**:
- Generic `open/closed` status. Rejected because it collapses human rejection and system failure.
- Free-form status text. Rejected because it is not auditable or reliable for metrics.

## Decision: Model review gates as first-class records

**Rationale**: Product, architecture, and quality are always required; compliance is automatically required when configured sensitive surfaces are detected. First-class gate records support assignee, decision, rationale, status, timestamps, and blocking issues.

**Alternatives considered**:
- Store gate decisions as comments only. Rejected because comments are not enough for deterministic approval checks.
- Require compliance for every cycle. Rejected because low-risk UI/refactor cycles should not be blocked by unnecessary compliance review.

## Decision: Keep generated changes review-only until explicit external authorization

**Rationale**: The agent can prepare changes in the sandbox/worktree, but no push, deployment, or irreversible action can happen until required gates are complete and a user with explicit repository/domain permission authorizes the action at execution time.

**Alternatives considered**:
- Let any reviewer authorize external actions. Rejected because review participation is not the same as repository/domain authority.
- Platform-admin-only authorization. Rejected because platform admins may not own the domain context and would become a bottleneck.

## Decision: Use HTTP contracts for cycle management

**Rationale**: CappyCloud exposes product workflows through FastAPI and the React frontend. HTTP contracts are enough for the MVP and align with existing conversation, repository, and admin APIs.

**Alternatives considered**:
- gRPC contract for product UI. Rejected because gRPC is currently internal to the agent runtime and sandbox bridge.
- Background-only implementation. Rejected because users need creation, review, authorization, and metrics surfaces.

## Decision: Use existing local quality gates

**Rationale**: The constitution and repository docs require `ruff`, `ruff format --check`, `mypy app/`, `pytest`, and frontend lint/build when `web/` changes. The feature touches both API and frontend.

**Alternatives considered**:
- Only API tests. Rejected because the frontend review workflow and typed API client are part of the user value.
