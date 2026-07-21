# Release Impact Matrix: OpenClaude v0.24 Chat Commands

## Implementation Readiness

| Theme | Decision | Implementation link | Validation |
|---|---|---|---|
| Slash command catalog | New chat UI | T037-T053 | T031-T036, T054 |
| `/model` and inactive provider profiles | CappyCloud-owned model picker and authorization | T009, T011, T018, T039 | T014, T020, T031 |
| `/ctx` context diagnostics | Chat command using CappyCloud conversation usage | T040 | T021, T032, T054 |
| `/cost` cost diagnostics | Chat command using provider-returned usage and catalog pricing | T040 | T021, T032, T054 |
| `/doctor` diagnostics | Visible but unavailable until a safe CappyCloud diagnostic path exists | T038, T041 | T031, T054 |
| `/bughunter`, `/bughunter-security`, `/bughunter-perf` | Visible, confirmation-gated, unavailable until mapped to safe backend workflow | T038, T041, T042 | T031, T032, T054 |
| `/set-context-window`, `/clear-context-window` | Visible, confirmation-gated, unavailable until CappyCloud owns context window override | T038, T041, T042 | T031, T032, T054 |
| `/goal` and session controls | Visible but unavailable because CappyCloud owns conversation/session state | T038, T041 | T031, T054 |
| `/update` and runtime update | Admin/operation only; production rollout excluded | T038, T041, T059-T072 | T055-T058, T070-T072 |
| Repo map intelligence | Runtime-only validation unless surfaced through a CappyCloud-owned panel | T075-T078 | T079, T088 |
| Local skills and PDF skill support | Runtime capability; no new end-user UI in this feature | T075-T078 | T079, T088 |
| Background sessions and branch/resume grouping | Existing chat/session UI validation, no new command execution path | T075-T078 | T071, T079 |
| WebSearch diagnostics and provider integrations | Provider enablement outside scope; diagnostics must be sanitized | T016, T041, T077 | T080, T088 |
| OAuth manual callback paste | Out of chat scope; never render raw callback payloads or tokens | T016, T077 | T080, T088 |
| Runtime cache, timeout, diff and stream fixes | Runtime build/smoke validation | T059-T072 | T070-T071, T087 |
| CappyCloud source-of-truth behavior | Preserve conversation, model, permission, tokens and cost outside OpenClaude state | T018-T030, T040, T044, T048 | T024, T029, T058, T085 |

## Command Family Links

| Family | Commands | Backend | Frontend | Runtime |
|---|---|---|---|---|
| Model | `/model` | T009, T011, T018, T039 | T045-T049 | T037-T038 |
| Context | `/ctx`, `/set-context-window`, `/clear-context-window` | T040-T042 | T045-T050 | T037-T038 |
| Cost | `/cost` | T040 | T045-T050 | T037-T038 |
| Diagnostics | `/doctor` | T041 | T045-T050 | T037-T038 |
| Bughunter | `/bughunter`, `/bughunter-security`, `/bughunter-perf` | T041-T042 | T045-T050 | T037-T038 |
| Goal/session | `/goal` | T041 | T045-T050 | T037-T038 |
| Update/runtime | `/update` | T041-T042 | T045-T050 | T059-T072 |
| Reports/repo map/background sessions | upstream runtime features | T075-T078 | T075-T078 | T059-T072 |

## Out-of-Scope Decisions

- Terminal-only commands remain visible as unavailable in the chat catalog because auto-running them would bypass CappyCloud permission, repository and audit boundaries.
- New providers from v0.20.0-v0.24.0 are not enabled by this feature; provider catalog and authorization stay in admin/model configuration.
- Production image push, deployment and `/update` runtime mutation are excluded; this work only builds and smokes a local validation image.
- OAuth manual callback paste is not exposed in normal chat. Any future operational UI must sanitize callback URLs, `code`, `state`, access tokens and refresh tokens before display.
