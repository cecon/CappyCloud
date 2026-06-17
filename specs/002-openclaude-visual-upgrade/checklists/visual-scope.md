# Visual Scope Checklist: OpenClaude v0.14.0

Each release item has exactly one chat UI scope decision.

| Done | Release item | Decision |
|---|---|---|
| [X] | diagnostics: request payload size breakdown | New chat visual |
| [X] | opengateway: API key on `/v1/*` and bearer auth | No new chat visual |
| [X] | xAI/Grok OAuth provider | No new chat visual |
| [X] | QueryGuard 5-minute timeout | Validate existing visual |
| [X] | Non-OpenAI providers skip `OPENAI_API_KEY` check | No new chat visual |
| [X] | Bash preserves stdout in non-zero exit error | Validate existing visual |
| [X] | Compaction clears native tool results | Validate existing visual |
| [X] | Built-in agents registered for Agent tool | Validate existing visual |
| [X] | Harden XAA OAuth callback state | No new chat visual |
| [X] | Input preserves split UTF-8 keypresses | No new chat visual |
| [X] | MiMo removes unsupported body fields and preserves reasoning | Validate existing visual |
| [X] | Monitor closes permission dialog after selection | Validate existing visual |
| [X] | Query stops repeated tool-failure loops | Validate existing visual |
| [X] | Recovery keeps thinking blocks on resume | Validate existing visual |
| [X] | Retry adjusts max_tokens on OpenRouter 402 | No new chat visual |
| [X] | stdin/MCP input freeze guard | No new chat visual |
| [X] | TaskListV2 label overflow fix | No CappyCloud chat visual |
| [X] | Blank `Read.pages` treated as omitted | No new chat visual |
| [X] | XML escaping handles null/undefined | No new chat visual |

## Review Notes

- The only new CappyCloud chat UI is the request payload diagnostic summary.
- Existing chat surfaces cover timeout/error, tool output, action-required,
  thinking/resume, usage, and cost states.
- Provider auth, OAuth, XML, stdin, and OpenClaude TUI-only changes remain out
  of CappyCloud chat scope unless they produce a normal streamed error.
