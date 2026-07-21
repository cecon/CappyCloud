# Data Model: OpenClaude v0.24 Chat Commands

## SlashCommand

Represents one upstream slash command discovered for the active runtime.

**Fields**

- `name`: canonical command name including leading `/`.
- `description`: Portuguese user-facing summary.
- `source`: `upstream`, `cappycloud`, or `runtime`.
- `category`: `model`, `context`, `cost`, `diagnostic`, `analysis`, `report`, `session`, `runtime`, `external`, or `other`.
- `arguments`: ordered list of argument descriptors.
- `availability`: current availability state.
- `requires_confirmation`: true for commands that alter state, cost, model, context, runtime, branch, session or external access.
- `confirmation_reason`: short Portuguese reason shown before execution when confirmation is required.
- `execution_mode`: `chat_action`, `runtime_command`, or `unavailable`.

**Validation Rules**

- `name` must start with `/` and be unique within one command catalog.
- Unavailable commands must include a non-empty Portuguese `unavailable_reason`.
- Commands without safe mappings must have `execution_mode = unavailable`.
- State-changing commands must set `requires_confirmation = true`.

## CommandArgument

Represents one argument accepted by a slash command.

**Fields**

- `name`: stable argument key.
- `label`: Portuguese label.
- `required`: whether execution is blocked without a value.
- `value_hint`: short input hint.
- `allowed_values`: optional finite set for menu-style values.
- `sensitive`: true when value must not be echoed in timeline/logs.

**Validation Rules**

- Required missing arguments block execution.
- Sensitive values cannot be rendered in command timeline events.

## CommandAvailability

Represents whether a command can execute for the active conversation.

**Fields**

- `state`: `available`, `needs_arguments`, `needs_confirmation`, `blocked`, or `unavailable`.
- `reason`: Portuguese explanation for blocked/unavailable states.
- `required_role`: optional role requirement.
- `required_capability`: optional runtime, model, repo or provider capability.

**State Transitions**

```text
unavailable -> available       # runtime/feature becomes supported
available -> needs_arguments   # user selects command with missing required args
needs_arguments -> needs_confirmation
available -> needs_confirmation
needs_confirmation -> available
available -> blocked           # authorization/runtime state changes
blocked -> available           # blocking condition resolved
```

## CommandExecutionEvent

Represents command execution feedback in the conversation timeline.

**Fields**

- `command_name`: command name.
- `status`: `started`, `waiting_for_input`, `completed`, `unavailable`, `failed`, or `cancelled`.
- `summary`: Portuguese visible summary.
- `details_markdown`: optional sanitized markdown for reports/diagnostics.
- `request_id`: correlation id when linked to an agent stream.
- `result_artifacts`: optional generated artifacts with safe display metadata.

**Validation Rules**

- Failed and unavailable events must include a user-actionable `summary`.
- `details_markdown` must be sanitized and must not include secrets, hidden prompts, raw OAuth callbacks or unauthorized repository contents.

## CommandCatalog

Represents the command list for one active conversation/runtime.

**Fields**

- `conversation_id`
- `runtime_version`
- `runtime_commit`
- `generated_at`
- `commands`

**Validation Rules**

- The catalog must include every discovered upstream command.
- The catalog may cache only as an optimization; runtime and authorization checks still happen before execution.

## AgentRuntimePin

Represents the selected OpenClaude runtime source.

**Fields**

- `version`: `v0.24.0`.
- `commit_sha`: `2ff93a10bf88ab6d7030fc4ade5316a7424fa2f9`.
- `source_url`: release/tag URL.
- `verified_at`: verification timestamp/date.
- `patch_audit_status`: `pending`, `passed`, or `blocked`.

## RuntimePatchAuditItem

Represents one local OpenClaude patch or inline source edit.

**Fields**

- `name`: patch file or inline edit label.
- `purpose`: permission, worktree, multimodal, usage, diagnostics, compatibility or other.
- `decision`: `retained`, `changed`, `removed`, or `obsolete`.
- `evidence`: command/build/test evidence.
- `risk`: short risk note.

## AuthorizedModelProfile

Represents a model/provider entry visible through CappyCloud.

**Fields**

- `model_id`
- `display_name`
- `provider`
- `active`
- `provider_active`
- `capabilities`
- `context_window`
- `max_output_tokens`
- `pricing`
- `unavailable_reason`

**Validation Rules**

- `/model` cannot select a model unless both model and provider are authorized for the user.
- Inactive provider profiles may be shown for explanation, but not selected.
