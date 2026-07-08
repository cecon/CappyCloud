# Research: OpenClaude v0.17.1 UI Debt Audit

## Decision: Pin OpenClaude to the v0.17.1 tag SHA

Use `1b7e55058cca57f2f83d7e229441631794286c1a` as the planned
`OPENCLAUDE_REF`. The current sandbox Dockerfile still uses
`670744fc70353f2270e86531dffa1c06f4fac79c`, which the spec records as the
v0.15.0 baseline.

**Rationale**: The feature target is explicitly v0.17.1, not v0.18.0. A commit
pin keeps Docker builds reproducible and reviewable while allowing local patch
audit against the exact upstream tree.

**Alternatives considered**: Using the moving tag name would be less traceable;
jumping to v0.18.0 would violate the spec scope.

## Decision: Keep CappyCloud as visible conversation source of truth

OpenClaude cache and session persistence must be disabled or constrained so
they support execution only. Visible history, active conversation, repository,
permission mode, selected model, usage, and cost remain owned by CappyCloud.

**Rationale**: Repository docs describe conversation permission mode and runtime
context as CappyCloud-owned behavior. The gRPC request already carries
`session_id`, `request_id`, optional model/provider fields, and
`permission_mode`, which gives CappyCloud enough context to govern visible
state.

**Alternatives considered**: Letting OpenClaude cache drive visible resume would
create two sources of truth and can show stale messages or the wrong permission
mode after a conversation switch.

## Decision: Surface fallback only from sanitized runtime metadata

Automatic provider/model fallback may be accepted only when the final model is
authorized in the CappyCloud catalog. The UI should show a sanitized notice only
when runtime metadata confirms a provider/model change.

**Rationale**: The project constitution and runtime docs require dynamic model
selection and provider-returned usage/pricing as product behavior. Silent
fallback would make the model label, capability, and cost misleading.

**Alternatives considered**: Blocking all fallback is simpler but loses a
runtime feature from v0.17.0. Allowing upstream fallback without CappyCloud
authorization breaks access control and cost accuracy.

## Decision: Treat `skill://` as an auditable source, not an active override

`skill://` and MCP-discovered skills can be displayed or audited only after
CappyCloud registration/authorization. They must not replace repository skills
or become active just because the runtime discovers them.

**Rationale**: Repo instructions state that active repo skills come from runtime
context, database, or versioned repo files. Unregistered runtime discovery would
make skill provenance unclear and hard to audit.

**Alternatives considered**: Auto-enabling MCP skills would be convenient but
would bypass repository-specific governance and could change agent behavior
without a visible admin decision.

## Decision: Validate existing UI before creating new surfaces

Most release items map to existing chat, model picker, admin, diagnostics, and
conversation search states. New UI work is limited to explicit gaps: fallback
notice, `skill://` provenance/admin audit, runtime cache/session state handling,
and hardened sanitized diagnostics where existing states are insufficient.

**Rationale**: The CappyCloud UI already renders stream events, tool activity,
action-required prompts, usage/cost, model picker states, attachments, and
conversation search. The safest path is to verify these states against the
runtime delta before adding parallel components.

**Alternatives considered**: Building new dedicated OpenClaude release screens
would add maintenance surface and is not required for terminal-only upstream
features.
