# Contract: Session Permission Mode

This contract covers the CappyCloud HTTP and frontend behavior for the
chat-level permission mode selector.

## Enum

```ts
type PermissionMode =
  | "request_permissions"
  | "accept_edits"
  | "plan"
  | "auto"
  | "bypass_permissions"
```

## Conversation response

`GET /api/conversations` and `POST /api/conversations` return:

```json
{
  "id": "uuid",
  "title": "Nova conversa",
  "permission_mode": "request_permissions"
}
```

Rules:

- `permission_mode` is always present.
- New conversations return `request_permissions`.
- Legacy rows with no stored mode are returned as `request_permissions`.

## Stream request

`POST /api/conversations/{conversation_id}/messages/stream`

```json
{
  "content": "Atualize a feature X",
  "model_id": "anthropic/claude-sonnet-4",
  "attachment_ids": ["uuid"],
  "permission_mode": "auto"
}
```

Rules:

- `permission_mode` is optional for backward compatibility.
- If present, it must match one of the enum values.
- If omitted, the backend uses the conversation's current mode.
- The backend persists the resolved mode on the conversation before dispatching
  the agent execution.
- Authorization rules for conversations, repositories, sandboxes, models, and
  attachments are unchanged.

## Frontend behavior

The chat UI shows a selector with Portuguese labels:

| Value | Label | Warning |
|---|---|---|
| `request_permissions` | Solicitar permissoes | none |
| `accept_edits` | Aceitar edicoes | caution |
| `plan` | Modo de planejamento | none |
| `auto` | Modo automatico | high-risk bypass |
| `bypass_permissions` | Ignorar permissoes | high-risk bypass |

Rules:

- The selector is visible before the first message in a new conversation.
- The selector is disabled while a stream is active unless the UI is only
  rendering the current mode.
- Changing the selector affects the next execution only.
- Warning severity is derived from the selected mode, not from provider type.

## Stream events

No new SSE event type is required for the base selector. Existing `status`,
`tool_start`, `tool_result`, `action_required`, `payload_diagnostic`, `error`,
and `done` events remain compatible.

When the OpenClaude startup warning is safely detected, runtime context is
surfaced through sanitized `status` metadata rather than a new event type:

```json
{
  "type": "status",
  "metadata": {
    "permission_warning": {
      "runtime_confirmed": true,
      "source": "openclaude_startup_alert"
    }
  }
}
```

Rules:

- The UI still derives severity from the selected session mode.
- If runtime context is absent, `runtime_confirmed` is false and the
  mode-derived warning still appears.
- Runtime context must not include raw container logs, provider keys, hidden
  prompts, repository contents, or tool inputs.
