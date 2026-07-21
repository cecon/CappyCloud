# UI Contract: Slash Commands In Chat

## Composer Trigger

- Typing `/` at the beginning of the input or immediately after a newline opens slash suggestions.
- A `/` in the middle of ordinary text remains plain text.
- Pasted multiline content beginning with `/` is preserved and must not execute automatically.

## Suggestion List

Each row shows:

- command name
- Portuguese description
- category indicator
- argument hint when applicable
- availability state
- unavailable reason when blocked/unavailable
- confirmation indicator when execution requires confirmation

The list must:

- filter by command name and description
- support keyboard and pointer selection
- preserve draft text, attachments, selected model and permission mode
- keep the footer/composer toolbar mounted while open
- avoid overlapping send/stop, attachment state, permission mode and runtime warnings

## Execution UX

### Available read-only command

1. User selects command.
2. Required arguments are inserted or requested inline.
3. User sends command.
4. Timeline shows command start and result.

### State-changing command

1. User selects command.
2. UI shows inline confirmation before execution.
3. User confirms or cancels.
4. If confirmed, timeline shows command start and result.
5. If cancelled, draft state remains understandable and no runtime action occurs.

### Unavailable command

1. User sees command in suggestions.
2. Row is disabled or selectable for details only.
3. UI shows Portuguese reason.
4. Command is not sent as plain chat text by accident.

## Timeline

Command output appears in the same conversation timeline as agent output.

Required states:

- started
- waiting for input
- completed
- unavailable
- failed
- cancelled

Reports and diagnostics render sanitized markdown. Errors must be actionable without raw secrets, hidden prompts, raw OAuth callbacks, unsanitized tool arguments or unauthorized repository contents.

## Accessibility And Localization

- All visible labels and errors are Portuguese.
- Keyboard users can open suggestions, move through rows, insert/execute and dismiss.
- Availability and confirmation states are announced through accessible text, not color alone.
- Focus returns predictably to the composer after selection, cancellation or execution.

## Regression States

Manual validation must cover:

- empty input `/`
- multiline input with `/`
- slash in URL/path/prose
- command requiring arguments
- unavailable terminal-only command
- state-changing command confirmation
- action-required prompt already pending
- streaming response in progress
- attachment present
- model fallback notice visible
- narrow viewport composer layout
