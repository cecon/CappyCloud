# Feature Specification: Agentic Delivery Factory

**Feature Branch**: `001-agentic-delivery-factory`

**Created**: 2026-06-16

**Status**: Draft

**Input**: User requested a specification based on the local PDF `C:/Users/cecon/Downloads/rewiring-software-delivery-for-the-agentic-era.pdf`. The PDF, published by McKinsey Technology in May 2026, describes a software delivery model with daily human review cycles, overnight agent execution, standardized handoffs, connected knowledge, and value capture through smaller teams and portfolio redesign.

## Clarifications

### Session 2026-06-16

- Q: What execution scope should the MVP support?→ A: Agents may generate changes in the cycle worktree/sandbox, but human review is required before any external action.
- Q: What should be the default scope for reusable knowledge?→ A: Reuse is limited to the authorized repository/domain; cross-repository reuse requires an explicit authorized relationship, and isolation must be enforced during knowledge retrieval before content reaches the agent.
- Q: Which review gates are mandatory in the MVP?→ A: Product, architecture, and quality gates are always required; compliance is triggered automatically when the cycle touches configured sensitive surfaces such as fiscal rules, electronic documents, tax parameters, or regulated customer data.
- Q: What minimum lifecycle states should an agentic delivery cycle support?→ A: Draft, Ready, Running, Review, Rework, Approved, Rejected, Cancelled, and Failed, with controlled valid transitions between states.
- Q: Who can authorize external actions?→ A: Only users with explicit permission for the repository or domain may authorize external actions, and only after all required gates are complete; authorization must be rechecked at the external action execution boundary.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Prepare an Agentic Delivery Cycle (Priority: P1)

A product owner starts a delivery cycle for a selected initiative by providing the business goal, target repositories, acceptance expectations, known constraints, and relevant source material. CappyCloud turns these inputs into a structured work package that agents can execute without requiring humans to translate context between each delivery stage.

**Why this priority**: The PDF states that agentic delivery only works when the path from requirements to code follows a standard structure and when humans can review clear outputs instead of manually coordinating every handoff.

**Independent Test**: Can be fully tested by creating a cycle with one selected repository, one business objective, acceptance criteria, and two evidence sources, then confirming that CappyCloud produces a complete, review-ready work package before agent execution begins.

**Acceptance Scenarios**:

1. **Given** a user has access to a repository and starts a new delivery cycle, **When** they provide the initiative goal, scope, acceptance criteria, and constraints, **Then** CappyCloud creates a structured work package that clearly identifies expected outputs, review gates, and required evidence.
2. **Given** a user provides incomplete or conflicting inputs, **When** they attempt to start the cycle, **Then** CappyCloud explains what is missing or inconsistent and prevents the cycle from being queued until the critical gaps are resolved.
3. **Given** source material is attached to the cycle, **When** the work package is prepared, **Then** CappyCloud records which sources are in scope and what each source is expected to support.

---

### User Story 2 - Review Agent Outputs With Traceability (Priority: P2)

A tech lead reviews the outputs produced by agents after an execution window. CappyCloud presents a consolidated review package with requirements changes, design decisions, code and test outcomes, risks, unresolved questions, and links back to the sources that justify each important recommendation.

**Why this priority**: The PDF emphasizes that humans should focus on judgment, architecture coherence, guardrails, and open decisions while agents perform structured execution at scale.

**Independent Test**: Can be tested by completing one agentic cycle and confirming that a reviewer can approve, reject, or request rework for each output using visible evidence and decision history.

**Acceptance Scenarios**:

1. **Given** an agentic cycle has produced outputs, **When** the tech lead opens the review package, **Then** they see the requested outcome, produced artifacts, test status, risks, and unresolved decisions in one place.
2. **Given** an output claims that a requirement or design choice is satisfied, **When** the reviewer inspects that claim, **Then** CappyCloud shows the evidence source or marks the claim as unsupported.
3. **Given** the reviewer rejects an output, **When** they record the reason, **Then** CappyCloud preserves the decision, sends the item back for rework, and keeps the original output available for audit.
4. **Given** a cycle touches a configured sensitive surface, **When** the review package is prepared, **Then** CappyCloud requires a compliance review gate in addition to product, architecture, and quality review.
5. **Given** a cycle has not completed its required review gates, **When** a user tries to mark it as approved, **Then** CappyCloud prevents the transition and explains which gates remain incomplete.
6. **Given** all required review gates are complete, **When** a reviewer without explicit repository or domain permission tries to authorize an external action, **Then** CappyCloud blocks the action and records the denied authorization attempt.

---

### User Story 3 - Preserve Knowledge Across Cycles (Priority: P3)

A delivery team uses CappyCloud to retain decisions, source links, constraints, review outcomes, and recurring lessons from each cycle so future agent work can reuse institutional knowledge instead of rediscovering context through manual interviews.

**Why this priority**: The PDF identifies structured, connected knowledge as the foundation of agent autonomy and warns against relying on fragmented documents and implicit subject matter expertise.

**Independent Test**: Can be tested by completing two cycles in the same domain and confirming that the second cycle can discover and reuse relevant decisions, constraints, and evidence from the first cycle.

**Acceptance Scenarios**:

1. **Given** a completed cycle contains decisions and evidence, **When** a user starts a related cycle, **Then** CappyCloud suggests relevant prior context and shows why it is related.
2. **Given** a decision was based on a specific source, **When** the source is no longer available or no longer supports the decision, **Then** CappyCloud marks the decision as needing review before reuse.
3. **Given** a user searches for why an item was prioritized, rejected, or changed, **When** they inspect the cycle history, **Then** CappyCloud shows the decision trail and the evidence used at the time.
4. **Given** reusable knowledge exists in another repository or domain, **When** there is no explicit authorized relationship to the current cycle context, **Then** CappyCloud does not make that knowledge available to the agent or reviewer.

---

### User Story 4 - Track Delivery Value and Capacity Impact (Priority: P4)

A delivery manager reviews cycle metrics to understand whether agent-assisted delivery is reducing handoffs, improving throughput, preserving quality, and freeing team capacity for higher-value work.

**Why this priority**: The PDF argues that productivity gains only create value when organizations consciously measure them and redeploy capacity toward roadmap acceleration, platform modernization, or new product work.

**Independent Test**: Can be tested by running multiple cycles and confirming that CappyCloud reports cycle duration, review outcomes, rework rate, unresolved blockers, evidence coverage, human intervention points, and cost.

**Acceptance Scenarios**:

1. **Given** multiple cycles have completed, **When** the manager opens the cycle summary, **Then** CappyCloud shows measurable trends for throughput, quality, rework, cost, and human review load.
2. **Given** a cycle required repeated human intervention, **When** the manager reviews its metrics, **Then** CappyCloud identifies the stages that caused friction and the reasons recorded by reviewers.
3. **Given** a team wants to compare agent-assisted delivery against its prior baseline, **When** baseline data is available, **Then** CappyCloud shows the change in cycle time, review effort, and rework volume.

### Edge Cases

- A selected repository has no active skills or repository-specific guidance.
- The attached source material conflicts with repository evidence or reviewer decisions.
- A cycle references external documentation that becomes unavailable after execution.
- Agent output is incomplete, unsupported by evidence, or fails the required quality checks.
- A user tries to reuse knowledge from a repository, domain, or conversation they cannot access.
- Semantically similar knowledge exists in another customer, ERP, repository, or domain but has not been explicitly authorized for the current context.
- A cycle starts as a low-risk change but agent analysis or generated changes reveal fiscal, electronic document, tax parameter, or regulated customer data impact.
- A user attempts to move a cycle directly from Draft, Ready, Running, Rework, Cancelled, Rejected, or Failed to Approved without passing through review and completing required gates.
- A reviewer has participated in the cycle but does not have explicit permission to authorize external actions for the affected repository or domain.
- A cycle runs longer than the planned execution window or is interrupted before producing a review package.
- Cost or usage data is missing from the model provider for one or more agent steps.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: CappyCloud MUST allow authorized users to create an agentic delivery cycle for a selected initiative and repository context.
- **FR-002**: CappyCloud MUST require each cycle to define a business goal, scope boundary, expected outputs, acceptance expectations, and responsible reviewers before execution.
- **FR-003**: CappyCloud MUST let users attach or reference supporting material such as product briefs, requirements, design notes, operational constraints, prior decisions, and external documentation.
- **FR-004**: CappyCloud MUST produce a structured work package that agents can use across requirements, design, implementation, validation, and review preparation stages.
- **FR-005**: CappyCloud MUST identify missing, conflicting, or unsupported critical inputs before a cycle is queued for execution.
- **FR-006**: CappyCloud MUST require product, architecture, and quality review gates for every cycle.
- **FR-007**: CappyCloud MUST produce a consolidated review package after agent execution that includes outputs, test or validation status, risks, open decisions, rework recommendations, and source evidence.
- **FR-008**: Reviewers MUST be able to approve, reject, comment on, or request rework for each major output in the review package.
- **FR-009**: CappyCloud MUST preserve the decision history for each cycle, including reviewer identity, decision time, stated rationale, and the affected output.
- **FR-010**: CappyCloud MUST link important claims, recommendations, and decisions to the evidence used to support them, or explicitly mark them as unsupported.
- **FR-011**: CappyCloud MUST make completed cycle knowledge discoverable for future related cycles while respecting repository, conversation, and user access boundaries.
- **FR-012**: CappyCloud MUST flag reused knowledge when its source is missing, stale, contradicted, or outside the user's accessible context.
- **FR-013**: CappyCloud MUST report cycle-level metrics for duration, review effort, rework volume, unresolved blockers, evidence coverage, model usage, and cost when provider usage is available.
- **FR-014**: CappyCloud MUST distinguish between agent-produced outputs, human decisions, external documentation evidence, and repository evidence.
- **FR-015**: CappyCloud MUST prevent automatic push, deployment, or irreversible repository changes unless a human explicitly approves that action for the cycle.
- **FR-016**: CappyCloud MUST preserve enough audit information for a user to explain what was requested, what agents produced, what humans accepted or rejected, and which sources supported the final outcome.
- **FR-017**: For the MVP, CappyCloud MUST allow agents to prepare repository changes only inside the cycle worktree or sandbox and keep those changes review-only until a human approves any external action.
- **FR-018**: Reusable knowledge MUST be retrieved only within the authorized repository or domain by default; cross-repository or cross-domain reuse MUST require an explicit authorized relationship before any candidate knowledge is exposed to the agent.
- **FR-019**: CappyCloud MUST automatically require a compliance review gate when cycle inputs, affected areas, agent outputs, or generated changes touch configured sensitive surfaces such as fiscal rules, electronic documents, tax parameterization, or regulated customer data.
- **FR-020**: CappyCloud MUST NOT rely on a reviewer manually remembering to classify a cycle as compliance-relevant when configured sensitive surfaces are detected.
- **FR-021**: CappyCloud MUST track each cycle using the lifecycle states Draft, Ready, Running, Review, Rework, Approved, Rejected, Cancelled, and Failed.
- **FR-022**: CappyCloud MUST allow only valid lifecycle transitions and MUST prevent final approval unless the cycle has passed through review and all required gates are complete.
- **FR-023**: CappyCloud MUST allow external action authorization only by users with explicit permission for the affected repository or domain.
- **FR-024**: CappyCloud MUST revalidate the user's explicit permission and required gate completion at the moment an external action is executed; hiding or disabling a user interface control MUST NOT be the only enforcement.

### Key Entities *(include if feature involves data)*

- **Agentic Delivery Cycle**: A bounded delivery effort for a selected initiative, including goal, scope, repository context, execution window, review gates, lifecycle status, valid transition history, and outcome.
- **Structured Work Package**: The normalized set of instructions, expectations, constraints, source references, and review criteria prepared before agent execution.
- **Evidence Source**: A repository artifact, attached document, external documentation record, operational signal, or prior decision used to support work in the cycle.
- **Agent Output**: A produced artifact or recommendation from an agent step, including its status, supporting evidence, unresolved questions, and validation result.
- **Review Decision**: A human approval, rejection, comment, or rework request tied to a specific output and rationale.
- **Review Gate**: A required checkpoint for product, architecture, quality, or compliance review, including status, responsible reviewer, rationale, and blocking issues.
- **External Action Authorization**: A permission-checked approval that allows a reviewed cycle to perform an action outside the review context, tied to the approving user, repository or domain, completed gates, time, and rationale.
- **Agentic Delivery Permission**: A feature-specific privileged permission for a repository or domain, separate from ordinary repository visibility, that grants `manage_sensitive_surfaces` or `authorize_external_action` capability.
- **Sensitive Surface**: A configured area where changes carry regulatory, fiscal, customer-data, or operational risk and therefore trigger additional review requirements.
- **Reusable Knowledge Item**: A decision, constraint, lesson, or source relationship from a completed cycle that can inform future related cycles, scoped to its authorized repository or domain unless an explicit relationship permits broader reuse.
- **Cycle Metric**: A measurable result for throughput, quality, review effort, cost, blockers, or rework associated with a cycle.

### Runtime Context, Security & Evidence *(mandatory when applicable)*

- **RC-001**: The cycle MUST use the repositories, repository skills, active MCP tools, selected model, and model cost context configured for the current conversation or environment; environment defaults are fallback only.
- **RC-002**: Users MUST only create, view, reuse, or approve cycle data for repositories and conversations they are authorized to access; repository/domain isolation MUST be enforced during knowledge retrieval before content is made available to an agent, and prompt guidance alone MUST NOT be treated as an access control.
- **RC-003**: External documentation may be cited only when it was actually attached, selected, or returned by a configured source during the cycle; CappyCloud MUST separate external documentation evidence from repository evidence and human decisions.
- **RC-004**: Sandbox, worktree, Git, network, push, deployment, and container-affecting actions MUST be visible in the cycle plan and require explicit human approval when they can change external state.
- **RC-005**: Compliance gate triggering is a security and governance control; when configured sensitive surfaces are detected, the gate MUST be required before final approval.
- **RC-006**: External action authorization is distinct from participation in review; a user may review outputs without being allowed to authorize actions for the affected repository or domain.
- **RC-007**: Existing repository access grants visibility only; sensitive surface management and external action authorization MUST require an explicit `AgenticDeliveryPermission` grant for the affected repository or domain, except where a platform admin is explicitly allowed to manage sensitive surface configuration.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: At least 90% of submitted cycles with complete inputs produce a review-ready work package without requiring manual reformatting by the user.
- **SC-002**: Reviewers can determine whether each major output is approved, rejected, or needs rework within 15 minutes for a single-repository cycle of moderate scope.
- **SC-003**: At least 95% of major claims in a review package are linked to evidence or explicitly marked as unsupported.
- **SC-004**: Teams can retrieve relevant decisions or constraints from prior related cycles in under 2 minutes during cycle preparation.
- **SC-005**: Cycle summaries show duration, rework rate, unresolved blockers, evidence coverage, and cost for at least 95% of completed cycles where provider usage data is returned.
- **SC-006**: 100% of generated repository changes remain confined to the review context until an auditable human approval authorizes any push, deployment, or irreversible external action.
- **SC-007**: Pilot teams reduce manual handoff clarification requests by at least 30% after using structured agentic cycles for four comparable initiatives.
- **SC-008**: At least 80% of pilot reviewers report that the review package makes agent output easier to evaluate than reviewing raw chat history alone.
- **SC-009**: 100% of knowledge retrieval attempts exclude unauthorized repositories and domains before any candidate content is presented to agents or reviewers.
- **SC-010**: 100% of cycles that touch configured sensitive surfaces require compliance review before final approval, while cycles with no sensitive surface impact can complete without compliance review.
- **SC-011**: 100% of final cycle outcomes distinguish human rejection, user cancellation, and system failure as separate measurable states.
- **SC-012**: 100% of external action attempts verify explicit repository or domain permission and completed required gates at execution time before changing external state.

## Assumptions

- The first version focuses on making agentic delivery cycles explicit, reviewable, and measurable inside CappyCloud; it does not attempt to redesign team staffing or portfolio governance by itself.
- The PDF is treated as a strategy input for product behavior, not as binding implementation guidance.
- Users already have authenticated access to CappyCloud and can select repositories according to the current environment configuration.
- Repository skills, MCP tools, external documentation sources, models, and costs remain dynamic runtime context rather than fixed product seeds.
- Baseline delivery metrics may be imported or manually recorded for comparison, but the feature remains useful without historical baseline data.
- Connected knowledge should start from live cycles and selected domains instead of requiring a complete enterprise-wide ontology before use.
