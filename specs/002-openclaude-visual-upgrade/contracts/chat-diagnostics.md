# Contract: Chat Payload Diagnostics

This contract defines the user-facing and stream-facing shape for request
payload size diagnostics.

## SSE Event

The chat stream may emit a diagnostic event before `done` or `error`.

```json
{
  "type": "payload_diagnostic",
  "diagnostics": {
    "total_size_bytes": 123456,
    "source": "openclaude",
    "generated_at": "2026-06-17T15:20:00Z",
    "categories": [
      {
        "key": "conversation_history",
        "label": "Historico da conversa",
        "size_bytes": 78000,
        "percentage": 63.2
      },
      {
        "key": "attachments",
        "label": "Anexos",
        "size_bytes": 32000,
        "percentage": 25.9
      },
      {
        "key": "repository_context",
        "label": "Contexto do repositorio",
        "size_bytes": 9000,
        "percentage": 7.3
      }
    ]
  }
}
```

### Rules

- `diagnostics` is optional in the stream as a whole, but required when
  `type = "payload_diagnostic"`.
- `total_size_bytes` is required and non-negative.
- `categories` is required and sorted descending by `size_bytes`.
- Compact UI renders total plus the first three categories.
- Expanded UI renders all categories.
- The event must not include raw prompt text, hidden instructions, provider
  keys, filenames, paths, repository URLs with credentials, raw tool payloads,
  or binary content.
- If multiple diagnostic events arrive in one turn, the latest valid sanitized
  object is the one persisted with the assistant message.

## Message History Response

`GET /api/conversations/{conversation_id}/messages` returns diagnostics on
assistant messages when they were persisted for the turn.

```json
{
  "id": "9d3e7f98-7f20-4da3-943d-8f9d66d816ad",
  "role": "assistant",
  "content": "Resposta do agente...",
  "created_at": "2026-06-17T15:20:12Z",
  "model_used": "anthropic/claude-sonnet-4",
  "prompt_tokens": 12000,
  "completion_tokens": 900,
  "cost_usd": 0.045,
  "payload_diagnostics": {
    "total_size_bytes": 123456,
    "source": "openclaude",
    "generated_at": "2026-06-17T15:20:00Z",
    "categories": [
      {
        "key": "conversation_history",
        "label": "Historico da conversa",
        "size_bytes": 78000,
        "percentage": 63.2
      }
    ]
  }
}
```

### Rules

- `payload_diagnostics` is `null` or omitted when no diagnostic is available.
- User messages should not carry payload diagnostics.
- Conversation usage totals continue to be based on token/cost fields only.
- Existing clients that ignore the new field continue to work.

## Frontend Type Contract

```ts
type PayloadSizeCategory = {
  key: string
  label: string
  size_bytes: number
  percentage?: number | null
}

type PayloadSizeBreakdown = {
  total_size_bytes: number
  categories: PayloadSizeCategory[]
  source?: string | null
  generated_at?: string | null
}

type ChatMessage = {
  id: string
  role: string
  content: string
  created_at: string
  model_used?: string | null
  prompt_tokens?: number
  completion_tokens?: number
  cost_usd?: number
  payload_diagnostics?: PayloadSizeBreakdown | null
}
```

## Error and Empty Behavior

- Missing diagnostics: render nothing.
- Empty categories with a total: compact UI may show only total and expandable
  details are disabled or empty.
- Malformed stream diagnostic: ignore the event and continue the chat.
- Unsafe category data: drop unsafe fields and retain only allowlisted key,
  label, and size values.
