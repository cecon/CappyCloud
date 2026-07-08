# Research: OpenClaude v0.15.0 Permission Mode Upgrade

## Decision: Pin OpenClaude v0.15.0 by tag SHA

**Rationale**: The sandbox build already pins OpenClaude through
`OPENCLAUDE_REF`. Tag lookup on 2026-06-17 returned v0.15.0 at
`670744fc70353f2270e86531dffa1c06f4fac79c`, which keeps builds reproducible
and reviewable.

**Alternatives considered**:

- Floating tag name: simpler but less reproducible when debugging a failed
  build.
- Latest main branch: rejected because it mixes unrelated upstream changes into
  this scoped upgrade.

## Decision: Store current permission mode on the conversation

**Rationale**: The product decision is "config por sessao". In CappyCloud, the
conversation is the durable chat session and is already returned to the UI after
reload. Storing the current mode there lets the selector survive refreshes and
lets the backend apply the same value the user sees.

**Alternatives considered**:

- Frontend-only state: rejected because the backend/runtime would not have a
  reliable source after reload or reconnect.
- Per-user global preference: rejected because new sessions must always default
  to `solicitar permissoes`.
- Sandbox-level default: rejected by clarification because mode is per session.

## Decision: Send permission mode in the stream request

**Rationale**: The stream request is already where the UI sends model selection
and attachments for a new execution. Including `permission_mode` there avoids a
separate "update session mode" round trip and guarantees each dispatch uses the
visible mode at send time.

**Alternatives considered**:

- Separate PATCH endpoint before sending: clearer separation, but adds an extra
  request and more failure states.
- Derive only from stored conversation value: works after reload but makes the
  UI update less atomic when the user changes mode and immediately sends.

## Decision: Use stable internal enum codes with Portuguese labels

**Rationale**: The UI text is Portuguese, but backend/protobuf contracts should
use stable ASCII codes: `request_permissions`, `accept_edits`, `plan`,
`auto`, and `bypass_permissions`. This keeps contracts easy to validate and
translate.

**Alternatives considered**:

- Persist Portuguese labels: rejected because labels can change and are harder
  to validate across API/protobuf/runtime.
- Numeric enum in HTTP API: rejected because it is less self-explanatory in
  logs and tests.

## Decision: Warning severity is mode-derived, not provider-derived

**Rationale**: Clarification selected "não classificar por provider". The
warning should be predictable: high-risk for `auto` and `bypass_permissions`,
lower-severity caution for `accept_edits`, and no high-risk warning for
`request_permissions` or `plan`.

**Alternatives considered**:

- Classify all non-Anthropic providers as third-party: safer but rejected by
  clarification.
- Maintain provider allowlist: adds administrative burden and can drift.
- Warn only when OpenClaude emits the startup warning: misses risk before the
  runtime signal is collected.

## Decision: Extend gRPC ChatRequest instead of relying on env vars

**Rationale**: Current auto-approve behavior is patched via
`OPENCLAUDE_AUTO_APPROVE`, which is process-wide. Session mode must be per
request, so the agent must pass it through `ChatRequest` and the OpenClaude
patch must apply behavior for that request only.

**Alternatives considered**:

- Mutate process env per request: risky with concurrent sessions and hard to
  reason about.
- Maintain separate gRPC methods: unnecessary protocol expansion for one piece
  of request context.

## Decision: Clean up legacy process-wide auto-approval parameters

**Rationale**: Leaving old sandbox parameters active after adding
`permission_mode` creates two sources of truth. A global default such as
`OPENCLAUDE_AUTO_APPROVE=1` could silently bypass the session selector and make
the UI warning inaccurate. The implementation must remove or neutralize those
legacy parameters in startup scripts, patches, and patch-generation helpers.

**Alternatives considered**:

- Keep the old env var as a fallback: rejected because it can override the
  per-session setting and hide incorrect runtime behavior.
- Rename the old env var to the new enum: rejected because request-scoped
  behavior cannot be safely represented by a process-wide environment value.

## Decision: Keep CappyCloud hard safety boundaries in all modes

**Rationale**: Even `ignorar permissoes` should not bypass CappyCloud product
guards such as repository access, worktree scope, sandbox isolation, secret
redaction, and explicit external-action gates. The selector controls OpenClaude
permission prompts, not platform authorization.

**Alternatives considered**:

- Treat bypass mode as disabling all checks: rejected as unsafe and contrary to
  the constitution.
- Hide bypass mode entirely: rejected because the user explicitly wants a Codex
  or Claude Code style selector.
