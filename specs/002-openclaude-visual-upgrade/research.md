# Research: OpenClaude v0.14.0 Chat Visual Upgrade

## Decision: Pin OpenClaude v0.14.0 by commit SHA

**Rationale**: The current sandbox build uses `OPENCLAUDE_REF` with a commit
SHA. Keeping that pattern makes Docker builds reproducible and avoids a moving
tag or branch changing the runtime without a CappyCloud code change. The spec
already records `refs/tags/v0.14.0` as
`66ed9b61dcefea4bd58d1c24011cf32015b0fb29`.

**Alternatives considered**:

- Use `v0.14.0` tag directly: easier to read, but less explicit if the upstream
  tag is ever rewritten.
- Use upstream `main`: rejected because it would include unplanned changes.

## Decision: Audit local OpenClaude patches after the ref bump

**Rationale**: The sandbox currently applies several local patches after
checkout. v0.14.0 includes fixes that may overlap with local patches or make
some patches fail to apply. The implementation must classify each patch as
still needed, upstreamed, obsolete, or requiring adjustment before the sandbox
image can be considered valid.

**Alternatives considered**:

- Keep all patches blindly: rejected because duplicate upstream changes can
  break `git apply` or reintroduce behavior v0.14.0 already fixed.
- Remove all patches blindly: rejected because CappyCloud-specific behavior
  such as multimodal, dynamic model/provider override, MCP integration, and
  worktree guards may still be required.

## Decision: Transport payload diagnostics as structured events

**Rationale**: The chat UI needs compact summary, expansion, persistence, and
reload behavior. These requirements are brittle if diagnostics arrive as
assistant text. A structured event lets the API sanitize, persist, and render
diagnostics without mixing operational metadata into the assistant answer.

**Alternatives considered**:

- Parse diagnostic text from the assistant stream: rejected as fragile and
  provider-language dependent.
- Show diagnostics only in logs: rejected by the spec because users need to see
  the largest payload category in the chat.
- Compute diagnostics only in the frontend: rejected because the frontend does
  not have safe access to all runtime context and must not receive raw prompt
  material.

## Decision: Persist diagnostics on assistant messages as JSONB

**Rationale**: Clarification requires the breakdown to survive a conversation
reload. The diagnostic belongs to a single agent turn, so storing it with the
assistant message keeps retrieval simple and keeps the existing `/messages`
history endpoint authoritative for the UI.

**Alternatives considered**:

- Persist only in `agent_events`: rejected because the message history endpoint
  would need extra event replay or correlation after reload.
- Create a separate `message_payload_diagnostics` table: rejected for v1 because
  the object is small, optional, and only used with one message.
- Persist on the user message: rejected because the visual treatment is shown
  as secondary context for the agent turn and usage/cost already live on the
  assistant message.

## Decision: Sanitize to category labels and numeric sizes only

**Rationale**: The runtime receives repository context, attachments, provider
configuration, hidden instructions, and tool outputs. The UI only needs total
size and safe category totals. Category keys and byte counts satisfy the UX
goal without exposing sensitive content.

**Alternatives considered**:

- Include file names, paths, or prompt excerpts: rejected due to privacy and
  cross-repository exposure risk.
- Include raw provider payload JSON: rejected because it may contain hidden
  prompts, tool inputs, or secrets.

## Decision: Compact UI shows total plus top three safe categories

**Rationale**: This matches clarification and keeps chat scanning fast. The
expanded state still exposes all safe categories for troubleshooting.

**Alternatives considered**:

- Show all categories by default: rejected because it can make normal chat turns
  noisy.
- Show only total by default: rejected because users could not identify the
  largest category quickly.

## Decision: Existing visual treatments remain the default for non-diagnostic fixes

**Rationale**: The release includes many behavior fixes whose user-visible
surface is already represented by session progress, tool rows, action-required
cards, errors, and usage footers. Duplicating UI for those fixes would create
unnecessary surface area.

**Alternatives considered**:

- Add individual cards for each fixed behavior: rejected as noisy and not
  justified by the release item matrix.
