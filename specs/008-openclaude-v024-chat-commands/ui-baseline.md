# UI Baseline: Chat Composer And Stream

## Files Reviewed

- `web/src/pages/ChatPage.tsx`
- `web/src/components/chat/ChatComposer.tsx`
- `web/src/components/chat/ChatMessage.tsx`
- `web/src/api.ts`

## Current Behavior

- `ChatPage.tsx` owns the active conversation state, selected model, permission mode, attachment tray, live usage, pending action-required prompts and send/stop lifecycle.
- `ChatComposer.tsx` is a compact composer component used by the chat page, while `ChatPage.tsx` also contains page-level composer rendering for current layouts.
- `web/src/api.ts` already parses stream events including `tool_start`, `tool_result`, `action_required`, `payload_diagnostic`, `done` and `error`.
- Usage and cost are rendered from conversation message data and `DoneEvent` metadata.

## Implementation Constraints

- Slash suggestions must not unmount or obscure selected model, permission mode, attachment state, send/stop action, runtime warnings or pending action-required replies.
- Slash suggestions must refresh or close when conversation, model, permission mode or runtime changes.
- Command events should use the existing timeline stream rather than a second live channel unless absolutely necessary.
