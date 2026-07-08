# Data Model: OpenClaude v0.15.0 Permission Mode Upgrade

## Conversation

Represents one durable chat session.

### New field

- `permission_mode`: string enum, required, default `request_permissions`.

### Allowed values

| Value | UI label | Meaning |
|---|---|---|
| `request_permissions` | Solicitar permissoes | Ask the user before permissioned actions. |
| `accept_edits` | Aceitar edicoes | Allow file edit actions with a lower-severity caution indicator. |
| `plan` | Modo de planejamento | Keep execution read-only/planning-oriented. |
| `auto` | Modo automatico | Automatically approve OpenClaude permission prompts, with high-risk warning. |
| `bypass_permissions` | Ignorar permissoes | Bypass OpenClaude permission prompts, with high-risk warning. |

### Validation rules

- New conversations default to `request_permissions`.
- Unknown values are rejected by API validation.
- The value returned by conversation list/detail APIs is always one of the
  allowed values.
- Changing the mode affects future executions only.

## Agent Execution Request

Represents one user message sent to the agent runtime.

### Relevant fields

- `content`: user message text.
- `model_id`: selected model, optional.
- `attachment_ids`: uploaded attachments, optional.
- `permission_mode`: selected session permission mode, required by the UI and
  defaulted by the backend when omitted for backward compatibility.

### Validation rules

- If omitted, `permission_mode` resolves to the conversation's current value or
  `request_permissions` for legacy rows.
- Before dispatch, the use case persists the selected mode on the conversation.
- The resolved mode is included in the pipeline body.

## Session Permission Warning

Represents the UI warning derived from the selected mode.

### Derived fields

- `severity`: `none`, `caution`, or `high_risk`.
- `label`: short user-facing label.
- `description`: sanitized explanatory text.
- `runtime_confirmed`: boolean, true only when the runtime reports the upstream
  startup alert or equivalent context.

### Derivation

| Permission mode | Severity |
|---|---|
| `request_permissions` | `none` |
| `plan` | `none` |
| `accept_edits` | `caution` |
| `auto` | `high_risk` |
| `bypass_permissions` | `high_risk` |

### Security rules

- Warning content never includes provider API keys, hidden prompts, repository
  file contents, raw tool inputs, or raw container logs.
- Provider classification is not used to determine severity.

## OpenClaude ChatRequest

Internal gRPC request sent from the CappyCloud agent to OpenClaude.

### New field

- `permission_mode`: string enum using the same stable codes as the HTTP API.

### Runtime mapping

- `request_permissions`: use OpenClaude's normal `ActionRequired` flow.
- `accept_edits`: auto-approve edit tools inside CappyCloud's hard boundaries;
  other permissioned actions still ask or follow runtime defaults.
- `plan`: prevent mutating actions and guide the agent to planning/read-only
  behavior.
- `auto`: auto-approve permission prompts inside CappyCloud's hard boundaries.
- `bypass_permissions`: bypass OpenClaude permission prompts inside CappyCloud's
  hard boundaries.

## Release Item UI Scope

Represents the reviewable classification of OpenClaude v0.15.0 release notes.

### Fields

- `title`: release item title.
- `category`: feature or bug fix.
- `source`: release URL or issue/commit reference.
- `decision`: new CappyCloud UI, validate existing UI, or no CappyCloud UI.
- `reason`: concise justification.

## Agent Runtime Pin

Represents the selected OpenClaude upstream revision.

### Fields

- `version`: `v0.15.0`.
- `tag_sha`: `670744fc70353f2270e86531dffa1c06f4fac79c`.
- `selected_at`: date of verification.
- `patch_audit_status`: retained, changed, removed, or obsolete for each local
  patch.
