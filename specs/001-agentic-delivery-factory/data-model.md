# Data Model: Agentic Delivery Factory

## AgenticDeliveryCycle

Represents a bounded delivery effort.

**Fields**
- `id`: UUID
- `conversation_id`: UUID, optional link to the originating conversation
- `created_by_user_id`: UUID
- `repository_ids`: list of UUIDs in scope
- `domain_key`: optional string for authorized domain grouping
- `title`: string
- `business_goal`: text
- `scope_boundary`: text
- `expected_outputs`: list of strings
- `acceptance_expectations`: list of strings
- `status`: `Draft | Ready | Running | Review | Rework | Approved | Rejected | Cancelled | Failed`
- `execution_window_started_at`: datetime, optional
- `execution_window_finished_at`: datetime, optional
- `created_at`: datetime
- `updated_at`: datetime

**Relationships**
- Has many `StructuredWorkPackage`, `AgentOutput`, `ReviewGate`, `ReviewDecision`, `CycleMetric`, `ExternalActionAuthorization`.
- References repositories and optional conversation context.

**Validation**
- `Ready` requires at least one repository, business goal, scope boundary, expected output, acceptance expectation, and required review gates.
- `Approved` requires status history through `Review` and all required gates approved.
- `Rejected`, `Cancelled`, and `Failed` are distinct final outcomes.

## LifecycleTransition

Records controlled lifecycle movement.

**Fields**
- `id`: UUID
- `cycle_id`: UUID
- `from_status`: lifecycle status
- `to_status`: lifecycle status
- `changed_by_user_id`: UUID, nullable for system failure transitions
- `reason`: text
- `created_at`: datetime

**Valid transitions**
- `Draft -> Ready | Cancelled`
- `Ready -> Running | Cancelled`
- `Running -> Review | Failed | Cancelled`
- `Review -> Rework | Approved | Rejected | Cancelled`
- `Rework -> Ready | Running | Cancelled`
- Final states `Approved`, `Rejected`, `Cancelled`, `Failed` do not transition further in the MVP.

## StructuredWorkPackage

Normalized package prepared before agent execution.

**Fields**
- `id`: UUID
- `cycle_id`: UUID
- `version`: integer
- `instructions`: text
- `constraints`: list of strings
- `review_criteria`: list of strings
- `source_summary`: JSON object
- `created_at`: datetime

**Validation**
- Latest version is the package used for agent execution.
- Source summary must reference only sources in scope for the user's repository/domain access.

## EvidenceSource

Source supporting a work package, output, decision, or knowledge item.

**Fields**
- `id`: UUID
- `cycle_id`: UUID
- `source_type`: `repository | attachment | external_doc | prior_decision | operational_signal`
- `repository_id`: UUID, optional
- `document_id`: UUID, optional
- `attachment_id`: UUID, optional
- `source_url`: string, optional
- `title`: string
- `scope_note`: text
- `available`: boolean
- `created_at`: datetime

**Validation**
- External documentation evidence must record the source actually selected or returned by a configured tool.
- Repository evidence must be tied to a repository in cycle scope.

## AgentOutput

Agent-produced artifact or recommendation.

**Fields**
- `id`: UUID
- `cycle_id`: UUID
- `output_type`: `requirements | design | code_change | test_result | risk | recommendation | summary`
- `title`: string
- `content`: text
- `worktree_path`: string, optional
- `validation_status`: `not_run | passed | failed | unsupported`
- `unsupported_claims_count`: integer
- `created_at`: datetime

**Relationships**
- Has many `AgentOutputEvidenceLink` records and review decisions.

**Validation**
- Code changes are review-only until external action authorization.
- Claims without evidence must be marked unsupported.

## AgentOutputEvidenceLink

Explicit relationship between an agent output claim and the evidence supporting it.

**Fields**
- `id`: UUID
- `agent_output_id`: UUID
- `evidence_source_id`: UUID
- `claim_summary`: text
- `support_status`: `supported | unsupported | contradicted | stale`
- `created_at`: datetime

**Validation**
- Every major claim in a review package must have at least one evidence link or be marked unsupported.
- Evidence links must reference evidence sources in the same cycle and authorized repository/domain scope.

## ReviewGate

Required checkpoint for cycle approval.

**Fields**
- `id`: UUID
- `cycle_id`: UUID
- `gate_type`: `product | architecture | quality | compliance`
- `status`: `pending | approved | rejected | blocked`
- `required`: boolean
- `trigger_reason`: text
- `assigned_user_id`: UUID, optional
- `decided_by_user_id`: UUID, optional
- `decision_rationale`: text, optional
- `decided_at`: datetime, optional

**Validation**
- Product, architecture, and quality gates are always required.
- Compliance gate is required when sensitive surfaces are detected.
- Final cycle approval requires all required gates to be approved.

## SensitiveSurface

Configured surface that triggers compliance review.

**Fields**
- `id`: UUID
- `repository_id`: UUID, optional
- `domain_key`: string, optional
- `name`: string
- `description`: text
- `match_rules`: JSON object
- `active`: boolean
- `created_at`: datetime

**Validation**
- Active surfaces may match cycle inputs, affected paths, generated changes, or agent outputs.
- Matches trigger a compliance gate deterministically.
- Surface management is restricted to users with an active `manage_sensitive_surfaces` `AgenticDeliveryPermission` grant for the affected repository or domain, or platform admins.

## AgenticDeliveryPermission

Feature-specific privileged permission for agentic delivery actions.

**Fields**
- `id`: UUID
- `user_id`: UUID
- `repository_id`: UUID, optional
- `domain_key`: string, optional
- `permission`: `manage_sensitive_surfaces | authorize_external_action`
- `granted_by_user_id`: UUID
- `active`: boolean
- `created_at`: datetime

**Validation**
- At least one of `repository_id` or `domain_key` is required.
- Existing `UserRepositoryAccess` remains the visibility/access check for repository data; this permission grants only the named privileged capability.
- Permission grants, revocations, and reactivations are platform-admin operations and must be audited through the normal API request context.
- `authorize_external_action` is required to authorize push, pull request, deployment, network call, container change, or other external state changes for the matching repository or domain.
- Platform admins may manage permission grants, but admin role alone is not treated as external action authorization unless an explicit active permission grant exists.

## ReviewDecision

Human decision on an output or gate.

**Fields**
- `id`: UUID
- `cycle_id`: UUID
- `agent_output_id`: UUID, optional
- `review_gate_id`: UUID, optional
- `decision`: `approve | reject | request_rework | comment`
- `rationale`: text
- `decided_by_user_id`: UUID
- `created_at`: datetime

**Validation**
- Rework decisions move the cycle to `Rework` when they block approval.
- Rejections preserve original output for audit.

## ReusableKnowledgeItem

Decision, lesson, constraint, or relationship that can inform future cycles.

**Fields**
- `id`: UUID
- `repository_id`: UUID
- `domain_key`: string, optional
- `cycle_id`: UUID
- `knowledge_type`: `decision | constraint | lesson | source_relationship`
- `title`: string
- `content`: text
- `evidence_source_ids`: list of UUIDs
- `active`: boolean
- `needs_review`: boolean
- `created_at`: datetime

**Validation**
- Retrieval must pre-filter by authorized repository/domain before candidate content reaches the agent.
- Cross-repository/domain reuse requires an explicit relationship.

## KnowledgeReuseRelationship

Explicit authorization for cross-repository/domain reuse.

**Fields**
- `id`: UUID
- `source_repository_id`: UUID
- `target_repository_id`: UUID
- `source_domain_key`: string, optional
- `target_domain_key`: string, optional
- `authorized_by_user_id`: UUID
- `reason`: text
- `active`: boolean
- `created_at`: datetime

## ExternalActionAuthorization

Approval to perform an action outside the review context.

**Fields**
- `id`: UUID
- `cycle_id`: UUID
- `action_type`: `push | pull_request | deployment | network_call | container_change | other`
- `requested_payload`: JSON object
- `authorized_by_user_id`: UUID
- `repository_id`: UUID, optional
- `domain_key`: string, optional
- `rationale`: text
- `authorized_at`: datetime
- `executed_at`: datetime, optional
- `execution_status`: `authorized | executed | denied | failed`

**Validation**
- Permission and required gate completion must be rechecked at execution time.
- Authorization requires an active `authorize_external_action` `AgenticDeliveryPermission` grant for the acting user and affected repository or domain.
- UI hiding is not sufficient enforcement.

## CycleMetric

Measurable cycle result.

**Fields**
- `id`: UUID
- `cycle_id`: UUID
- `metric_name`: string
- `metric_value`: numeric or text
- `metric_unit`: string
- `source`: `system | provider_usage | reviewer | imported_baseline`
- `created_at`: datetime

**Validation**
- Provider cost uses real provider usage when available.
- Missing cost/usage is recorded as unavailable rather than estimated as fact.
