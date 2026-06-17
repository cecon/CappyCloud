# Data Model: OpenClaude v0.14.0 Chat Visual Upgrade

## Entity: Message

Existing chat message persisted in the `messages` table and returned by the
conversation history endpoint.

### Added Field

- `payload_diagnostics`: nullable object. Present only on assistant messages
  when a safe payload size breakdown is available for that turn.

### Validation Rules

- Must be `null` or a valid `PayloadSizeBreakdown`.
- Must not be included in the LLM conversation history sent back to the agent.
- For user messages, default is `null`.
- For assistant error messages, may be present if diagnostics were received
  before the error.

## Entity: PayloadSizeBreakdown

Safe per-turn summary of request payload size.

### Fields

- `total_size_bytes`: integer, required, `>= 0`.
- `categories`: list of `PayloadSizeCategory`, required, may be empty only when
  total exists but no safe category detail is available.
- `source`: string, optional. Expected values include `openclaude` or
  `cappycloud`.
- `generated_at`: ISO timestamp string, optional.

### Validation Rules

- `total_size_bytes` must be non-negative.
- Category values must be sorted descending by `size_bytes` when persisted or
  before rendering.
- Compact display uses the first three categories after sorting.
- Expanded display uses all categories in the object.
- The object must not contain raw prompts, tool input/output, filenames, paths,
  provider keys, repository URLs with credentials, or binary attachment data.

## Entity: PayloadSizeCategory

One safe bucket in the payload size breakdown.

### Fields

- `key`: stable string identifier such as `user_message`, `conversation_history`,
  `repository_context`, `attachments`, `tool_results`, `runtime_context`, or
  `other`.
- `label`: user-facing Portuguese label.
- `size_bytes`: integer, required, `>= 0`.
- `percentage`: number, optional, `0 <= percentage <= 100`.

### Validation Rules

- `key` must come from an allowlist or be normalized to `other`.
- `label` must be a safe category label, not user or repository content.
- `size_bytes` must be non-negative.
- If `percentage` is present, it is derived from
  `size_bytes / total_size_bytes`.

## Entity: AgentEvent

Existing persisted stream event in `agent_events`.

### Added Event Type

- `payload_diagnostic`: event data contains a `PayloadSizeBreakdown` object.

### Validation Rules

- Event data must be sanitized before it is written.
- Event data shape must match the SSE contract.
- Unknown or malformed diagnostic events must be ignored rather than breaking
  the chat stream.

## State Transitions

1. Diagnostic absent: no `payload_diagnostic` event and no message metadata.
2. Diagnostic received during stream: event is normalized and sent to the UI.
3. Assistant message saved: latest safe diagnostic for the turn is persisted on
   the assistant message.
4. Conversation reloaded: history endpoint returns the persisted diagnostic.
5. Diagnostic malformed or unsafe: event is dropped or reduced to safe
   categories, and chat continues without an empty diagnostic container.
