# API Contract: Chat Slash Commands

This contract describes product behavior. Exact router/module placement belongs to tasks, but backend business rules must live in use cases.

## Command Catalog

### Request

```http
GET /api/conversations/{conversation_id}/commands
Authorization: Bearer <token>
```

### Response

```json
{
  "runtime_version": "v0.24.0",
  "runtime_commit": "2ff93a10bf88ab6d7030fc4ade5316a7424fa2f9",
  "generated_at": "2026-07-20T00:00:00Z",
  "commands": [
    {
      "name": "/model",
      "description": "Escolher ou inspecionar modelos disponiveis",
      "category": "model",
      "source": "upstream",
      "arguments": [
        {
          "name": "model",
          "label": "Modelo",
          "required": false,
          "value_hint": "ID ou alias do modelo",
          "allowed_values": [],
          "sensitive": false
        }
      ],
      "availability": {
        "state": "available",
        "reason": null,
        "required_role": null,
        "required_capability": "authorized_model_catalog"
      },
      "requires_confirmation": true,
      "confirmation_reason": "Pode alterar o modelo da conversa.",
      "execution_mode": "chat_action"
    }
  ]
}
```

### Rules

- The response includes every upstream slash command discovered for the runtime.
- Commands that cannot execute safely return `execution_mode = "unavailable"` and an availability reason.
- Availability is conversation-specific and must account for user, repository, sandbox, selected model, provider and runtime state.
- The frontend may cache this response briefly but must refresh on conversation/runtime/model/permission changes.

## Command Execution

### Request

```http
POST /api/conversations/{conversation_id}/commands/execute
Authorization: Bearer <token>
Content-Type: application/json
```

```json
{
  "command": "/ctx",
  "arguments": {},
  "confirmed": false,
  "client_request_id": "uuid"
}
```

### Response: Needs Confirmation

```json
{
  "status": "needs_confirmation",
  "confirmation": {
    "message": "Este comando altera o contexto da conversa.",
    "confirm_label": "Executar",
    "cancel_label": "Cancelar"
  }
}
```

### Response: Accepted

```json
{
  "status": "accepted",
  "stream": {
    "conversation_id": "uuid",
    "client_request_id": "uuid"
  }
}
```

### Response: Unavailable

```json
{
  "status": "unavailable",
  "message": "Este comando existe no OpenClaude, mas nao possui execucao segura no chat do CappyCloud."
}
```

### Rules

- Backend revalidates authorization and availability on every execution request.
- Missing required arguments return a user-facing validation error and do not execute.
- `confirmed = true` is required only after the server first returns `needs_confirmation`.
- Command execution must not store sensitive arguments in user-visible messages.

## Stream Events

Command execution may use the existing message stream or emit command-specific SSE events through the same conversation timeline contract.

```json
{ "type": "command_start", "command": "/doctor", "label": "Diagnostico iniciado" }
```

```json
{
  "type": "command_result",
  "command": "/doctor",
  "status": "completed",
  "summary": "WebSearch disponivel",
  "details_markdown": "Resumo sanitizado..."
}
```

```json
{
  "type": "command_result",
  "command": "/update",
  "status": "unavailable",
  "summary": "Atualizacao de runtime nao esta habilitada neste ambiente."
}
```

### Rules

- Existing stream events remain valid: `status`, `text`, `tool_start`, `tool_result`, `action_required`, `payload_diagnostic`, `done`, `error`.
- Command result details must be sanitized before reaching the browser.
- Timeline must not duplicate a command as both a user text message and a command event unless the UI intentionally displays the user command text once.
