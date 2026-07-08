# Data Model: OpenClaude v0.17.1 UI Debt Audit

## AgentRuntimePin

- `name`: runtime identifier, expected `openclaude`.
- `version`: target upstream version, expected `v0.17.1`.
- `tag_sha`: pinned upstream commit, expected
  `1b7e55058cca57f2f83d7e229441631794286c1a`.
- `source_url`: upstream repository or release URL.
- `patch_audit_status`: `pending`, `retained`, `changed`, `removed`, or
  `obsolete`.

Validation rules:
- The sandbox build must use a commit SHA, not an unpinned branch.
- Every local patch must have an audit decision before implementation is ready.

## ReleaseDeltaItem

- `version`: upstream release version.
- `title`: release item summary.
- `source_evidence`: release note or tag evidence.
- `category`: feature, bug fix, security, provider, model, runtime, UI, docs, or
  operation.
- `ui_decision`: `new_ui_debt`, `validate_existing_ui`, `runtime_only`, or
  `outside_scope`.
- `reason`: CappyCloud-specific explanation.

Validation rules:
- Every item from v0.16.0, v0.16.1, v0.17.0, and v0.17.1 must have exactly one
  UI decision.
- New UI debt must map to an independently testable user outcome.

## RuntimeSessionState

- `conversation_id`: CappyCloud conversation identifier.
- `session_id`: runtime session/worktree identifier.
- `request_id`: per-turn trace identifier.
- `permission_mode`: one of `request_permissions`, `accept_edits`, `plan`,
  `auto`, or `bypass_permissions`.
- `visible_status`: `startup`, `active`, `resume`, `retry`, `action_required`,
  `cancelled`, `failed`, or `done`.
- `source_of_truth`: expected `cappycloud`.

Validation rules:
- OpenClaude cache/session state must not replace CappyCloud persisted history.
- Conversation switch and reload must show the active conversation's messages,
  permission mode, progress, and latest terminal state.

## ProviderFallbackNotice

- `selected_model_id`: model requested by the user or conversation.
- `final_model_id`: model confirmed by runtime/provider.
- `reason`: sanitized reason such as rate limit or provider unavailable.
- `authorized`: whether the final model is allowed by CappyCloud catalog/access.
- `usage_source`: provider usage metadata used for cost.
- `display_status`: hidden, shown, or blocked.

Validation rules:
- Show a notice only when the final model differs from the selected model and
  the final model is authorized.
- Block and show an actionable error when no authorized fallback exists.
- Never display provider keys, hidden prompts, raw logs, or unsanitized tool
  input.

## ModelCatalogEntry

- `model_id`: provider model slug visible to users.
- `provider`: provider/catalog owner.
- `capabilities`: text, vision, embeddings, large context, or provider-specific
  capabilities.
- `status`: active, inactive, retired, unavailable, or pending sync.
- `pricing`: input/output pricing from the current catalog.
- `default_eligibility`: text, vision, embedding, or none.
- `access_policy`: global/tier/user authorization metadata.

Validation rules:
- Upstream provider discovery cannot make a model visible unless CappyCloud
  authorizes it.
- Retired or unavailable models in old conversations must be explained without
  silent substitution.

## RuntimeSkillSource

- `name`: skill identifier.
- `origin`: repository file, sandbox global, database registration, or
  registered `skill://` resource.
- `authorized`: whether CappyCloud allows the source for the active context.
- `active`: whether it can affect the prompt/runtime.
- `audit_label`: user/admin-visible source label.

Validation rules:
- Repository skills remain authoritative for selected repos.
- `skill://` sources are audit-visible only until explicitly registered and
  authorized.

## SanitizedRuntimeDiagnostic

- `source`: openclaude, cappycloud, provider, sandbox, tool, or catalog.
- `code`: stable diagnostic code.
- `message`: user-facing Portuguese message.
- `metadata`: allowlisted key/value details.
- `severity`: info, warning, error.

Validation rules:
- Diagnostics must not include secrets, hidden prompts, raw logs, repository
  file contents, or raw tool input bodies.
- Tool errors and provider refusals should remain actionable after truncation.
