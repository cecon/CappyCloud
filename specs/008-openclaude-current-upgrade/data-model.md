# Data Model: OpenClaude Current Upgrade UI Readiness

## OpenClaude Release Target

Represents the upstream version selected for this feature.

**Fields**

- `version`: Frozen release version, `0.27.0`.
- `tag_commit`: Upstream tag commit SHA.
- `verified_at`: Date the target was verified.
- `source_urls`: External evidence used for version, changelog and tag data.
- `scope_status`: `frozen`, `superseded`, or `requires-new-decision`.

**Validation Rules**

- `version` must remain `0.27.0` for this feature.
- Any later version requires a new explicit product decision before entering
  scope.

## Runtime Baseline

Represents the currently observed OpenClaude version used as the upgrade
starting point.

**Fields**

- `environment`: Environment where the baseline was observed.
- `version`: Observed OpenClaude package version.
- `commit`: Observed runtime commit.
- `observed_at`: Date/time of observation.
- `source`: `production-container`, `local-dockerfile`, or `build-artifact`.
- `mismatch_notes`: Explanation when local source and running image differ.

**Validation Rules**

- Planning and implementation must re-check the baseline before code changes
  that depend on it.
- Mismatches must be visible in review artifacts.

## Release Theme

Represents a grouped upstream change from OpenClaude 0.25.0 through 0.27.0.

**Fields**

- `version`: Release where the theme appears.
- `name`: Short title.
- `source_summary`: Evidence-backed description.
- `affected_surface`: `chat`, `admin-provider`, `model-picker`,
  `sandbox-runtime`, `documentation`, or `none`.
- `ui_decision`: `adapt-ui`, `validate-existing`, `runtime-only`, or
  `out-of-scope`.
- `rationale`: Why the decision fits CappyCloud.

**Relationships**

- May create one or more `UI Adaptation Item`.
- May require one or more `Validation Scenario`.

## UI Adaptation Item

Represents a product-visible UI change required by the release delta.

**Fields**

- `title`: User-facing adaptation goal.
- `user_story`: Linked user story from the spec.
- `surface`: Chat, admin provider, model catalog or documentation.
- `required_before_upgrade`: Boolean.
- `deferred_reason`: Reason when not required before local validation.
- `access_scope`: `all-users`, `admin-only`, or `demo/reviewer`.

**Validation Rules**

- Items with `admin-only` access must not appear in regular user flows.
- Items required before upgrade must have a quickstart validation scenario.

## Chat Activity State

Represents visible execution state in the conversation.

**Fields**

- `turn_id`: Parent conversation turn.
- `state`: `loading`, `streaming`, `tool-running`, `subagent-group`,
  `permission-request`, `permission-timeout`, `stalled`, `canceled`,
  `failed`, or `done`.
- `label`: Portuguese user-facing short label.
- `detail`: Sanitized descriptive text.
- `started_at`: First observed time.
- `updated_at`: Last observed time.
- `terminal`: Whether this state ends the turn.
- `collapsible`: Whether details can be expanded/collapsed.

**State Transitions**

- `loading` -> `streaming` or `tool-running` or `failed`
- `tool-running` -> `subagent-group` or `permission-request` or `stalled` or
  `failed` or `done`
- `subagent-group` -> `tool-running` or `failed` or `done`
- `permission-request` -> `tool-running` or `permission-timeout` or `canceled`
- `stalled` -> `tool-running` or `failed` or `canceled`
- `failed`, `canceled`, `done` are terminal

**Validation Rules**

- `detail` must be sanitized before display.
- Subagent activity must be grouped and collapsible within the parent turn.

## Context Visibility Indicator

Represents discrete execution-time context/token feedback.

**Fields**

- `turn_id`: Parent conversation turn.
- `label`: Example: `Processando contexto`.
- `current_value`: Optional context/token progress value when available.
- `limit_value`: Optional context/token limit when available.
- `percent`: Optional bounded percentage.
- `financial`: Always `false`.
- `visible_phase`: `during-execution`.

**Validation Rules**

- Must not be presented as cost.
- Must not replace final provider usage or persisted cost.
- Must not block reading the latest assistant content.

## Provider Auth State

Represents administrator-only provider setup/authentication status.

**Fields**

- `provider_id`: Provider identity.
- `status`: `not-configured`, `credential-required`,
  `authentication-pending`, `authenticated`, `failed`, or `disabled`.
- `admin_message`: Sanitized administrator-facing message.
- `next_action`: Optional administrator action.
- `visible_to`: Always `admin`.
- `secret_visible`: Always `false`.

**Validation Rules**

- Regular users must not see onboarding/OAuth state.
- Admin messages must not include keys, tokens or callback secrets.

## Model Catalog Entry

Represents a model option governed by CappyCloud.

**Fields**

- `model_id`: CappyCloud model identifier.
- `provider_id`: Provider that serves the model.
- `upstream_name`: Provider/upstream model name.
- `status`: `active`, `disabled`, `retired`, `auth-required`, or
  `unknown-pricing`.
- `capabilities`: Text, vision, tool-use or other supported capabilities.
- `context_limit`: Optional context limit.
- `pricing_status`: `known`, `unknown`, or `not-applicable`.
- `visible_to_user`: Boolean determined by authorization.

**Validation Rules**

- Upstream models are not selectable until authorized in CappyCloud.
- Unknown pricing/capabilities must be explicit in admin/model states.

## Rollout/Rollback Runbook

Represents the production execution guide delivered for later use.

**Fields**

- `prerequisites`: Required checks before rollout.
- `deployment_steps`: Ordered execution steps.
- `validation_checks`: Checks after deployment.
- `rollback_triggers`: Conditions that require rollback.
- `rollback_steps`: Ordered recovery steps.
- `owner_notes`: Human-readable notes for the operator.

**Validation Rules**

- Must not execute production deployment as part of this feature.
- Must include local validation evidence as a prerequisite.
