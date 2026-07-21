# Research: OpenClaude v0.24 Chat Commands

## Decision: Target OpenClaude v0.24.0

**Rationale**: The user asked for the latest OpenClaude. On 2026-07-20, release verification identified `v0.24.0` as latest and `git ls-remote` returned `refs/tags/v0.24.0` at `2ff93a10bf88ab6d7030fc4ade5316a7424fa2f9`. Repository evidence shows `services/sandbox/Dockerfile` still pins `OPENCLAUDE_REF=1b7e55058cca57f2f83d7e229441631794286c1a`, the previous v0.17.1 target.

**Alternatives considered**:

- Stay on v0.17.1 and only add UI commands: rejected because the request is explicitly an upgrade to latest.
- Retarget to any newer release during implementation automatically: rejected because runtime upgrade evidence and patch audit must be explicit.

## Decision: Discover all upstream commands, gate execution

**Rationale**: Clarification chose to expose all discovered upstream commands in the chat catalog, marking unavailable those that cannot execute safely in the CappyCloud chat. This avoids hiding terminal-only behavior while preserving product safety.

**Alternatives considered**:

- Curated MVP allowlist: safer but rejected by clarification.
- Frontend-only documentation list: insufficient because command availability depends on runtime, conversation, authorization and sandbox state.

## Decision: Backend-owned command contract

**Rationale**: Command availability depends on user role, repository access, selected model, runtime state, sandbox worktree and whether a command has a safe headless path. Those rules are product behavior and must live in API use cases or runtime adapters, not in frontend-only filtering. This aligns with the repository rule that business logic belongs in `services/api/app/application/use_cases/`.

**Alternatives considered**:

- Parse `/` directly in `web/src/pages/ChatPage.tsx`: rejected because it would duplicate authorization and availability rules.
- Send slash text to OpenClaude unchanged: rejected because unavailable commands could run as plain text or bypass CappyCloud gates.

## Decision: Inline confirmation for state-changing commands only

**Rationale**: Clarification chose confirmation for commands that alter state, cost, model, context, runtime, branch, session or external access. Read-only diagnostics can remain quick. This preserves UX speed while protecting high-impact operations.

**Alternatives considered**:

- Confirm every command: too slow for diagnostics and discovery.
- Rely only on permission mode: insufficient for commands that change CappyCloud-owned state or external access.

## Decision: Slash trigger default

**Rationale**: The user moved to planning before answering the trigger clarification. The planning default is to open suggestions when `/` is at the beginning of the input or immediately after a newline. This handles command-first messages and multiline command blocks without interrupting ordinary text containing slashes.

**Alternatives considered**:

- Trigger anywhere: too noisy for URLs, paths and prose.
- Trigger only in empty input: too restrictive for multiline command workflows.
- Button-only trigger: conflicts with the explicit request to bring `/` commands to the input.

## Decision: Runtime patch audit before implementation

**Rationale**: `services/sandbox/Dockerfile` applies several local patches and inline `perl` edits over OpenClaude source. The v0.24.0 upgrade must classify each local patch as retained, changed, removed or obsolete before the runtime is considered ready. Relevant existing patch files include `grep-tool-n-alias.patch`, `multimodal-proto.patch`, `multimodal-grpc-handler.patch`, `read-empty-pages.patch` and additional patch files in `services/sandbox/patches/`.

**Alternatives considered**:

- Update the SHA and fix build failures reactively: rejected because patch drift could silently weaken permission, worktree, multimodal or stream behavior.

## Decision: Preserve existing SSE stream as primary timeline transport

**Rationale**: `web/src/api.ts` already handles status, text, tool start/result, action required, payload diagnostics, done and error events from `POST /api/conversations/{id}/messages/stream`. Command execution results should use this timeline model where possible, extending event payloads only when a command-specific state cannot be represented.

**Alternatives considered**:

- Separate WebSocket or polling channel: rejected as unnecessary and more complex for this feature.

## Decision: No provider enablement in this feature

**Rationale**: v0.18.0 through v0.24.0 mention new providers and provider profile behavior. CappyCloud provider/model visibility is governed by the authorized catalog and real pricing/capabilities. Runtime support does not imply user enablement.

**Alternatives considered**:

- Automatically expose every new upstream provider: rejected because it bypasses admin configuration, credentials and model access policy.
