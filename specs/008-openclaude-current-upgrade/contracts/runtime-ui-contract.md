# Runtime UI Contract: OpenClaude 0.27.0 Readiness

This contract defines the user-visible behavior CappyCloud must preserve or add
when upgrading OpenClaude from the 0.24.0 baseline to the frozen 0.27.0 target.
It is implementation-agnostic and should guide API, agent bridge, frontend and
manual validation tasks.

## Chat Timeline Contract

### Source Of Truth

- The CappyCloud conversation remains the visible source of truth.
- OpenClaude session/cache/history cannot replace CappyCloud-visible messages,
  selected repositories, selected model, permission mode, usage or cost.
- Runtime events may enrich the current turn only after sanitization.

### Required Turn States

| State | User-visible expectation |
|---|---|
| `loading` | The turn has started and the user sees that work is beginning. |
| `streaming` | Assistant content is arriving or expected. |
| `tool-running` | A tool is active and the UI communicates ongoing work. |
| `subagent-group` | Auxiliary work appears grouped and collapsible inside the parent turn. |
| `permission-request` | User action is required before a tool proceeds. |
| `permission-timeout` | The request expired and the user sees an actionable explanation. |
| `stalled` | Work has not progressed recently but is not yet terminal. |
| `canceled` | The user or system canceled the turn. |
| `failed` | The turn ended with a sanitized failure. |
| `done` | The turn ended successfully and final metadata can be shown. |

### Subagent Activity

- Subagent activity must not become separate top-level conversation messages.
- Each subagent group must remain associated with its parent turn.
- Expanded details may show sanitized names, status and summary, but not raw
  logs, hidden prompts, secrets or unauthorized repository content.

## Context Indicator Contract

- The context/token indicator is visible only during execution.
- The indicator is discrete and must not crowd the composer or main answer.
- Acceptable labels include `Processando contexto` or `Contexto usado`.
- If numeric values are available, they are progress/context values only.
- The indicator must never display or imply financial cost.
- Final usage and cost remain tied to provider-returned usage and CappyCloud
  catalog pricing.

## Tool And Runtime Error Contract

Runtime guard, tool failure, permission timeout and provider error messages must:

- Be actionable in Portuguese on user-facing surfaces.
- Avoid secrets, API keys, OAuth tokens, hidden prompts and raw logs.
- Avoid raw command inputs unless already authorized and necessary.
- Avoid repository file contents beyond the authorized conversation output.
- Preserve final turn status even when intermediate tool events fail.

## Provider And Model UI Contract

### Regular Users

- See only models/providers authorized by CappyCloud.
- Do not see provider onboarding, OAuth or credential setup flows.
- See catalog-governed unavailable/disabled states when a selected option is no
  longer usable.

### Administrators

- Can see provider states when applicable:
  - `not-configured`
  - `credential-required`
  - `authentication-pending`
  - `authenticated`
  - `failed`
  - `disabled`
- Can see sanitized next actions for provider setup or repair.
- Never see raw secrets or reusable credentials in state messages.

## Branding And Terminal-Only Contract

- CappyCloud visual identity remains authoritative.
- OpenClaude buddy companions, startup logo changes and upstream web identity
  are out of scope for CappyCloud UI.
- Slash commands and terminal-only features become CappyCloud UI only when
  mapped to an explicit product outcome in a later spec or design decision.

## Rollout Boundary Contract

- This feature may build and validate locally.
- This feature must not deploy to production.
- A rollout/rollback runbook is required for later execution and must include
  prerequisites, steps, validation checks, rollback triggers and rollback steps.
