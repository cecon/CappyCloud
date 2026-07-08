# Quickstart: OpenClaude v0.17.1 UI Debt Audit

## Prerequisites

- Docker available locally.
- Backend and frontend dependencies installed for the existing project.
- OpenRouter/provider credentials configured for the normal local environment.
- A sandbox/repository/conversation setup that can run at least one chat turn.

## 1. Verify Runtime Pin

Check that `services/sandbox/Dockerfile` uses:

```bash
OPENCLAUDE_REF=1b7e55058cca57f2f83d7e229441631794286c1a
```

Expected result: the pin matches the v0.17.1 tag SHA recorded in the spec and
the patch audit lists every local patch as retained, changed, removed, or
obsolete.

## 2. Build Sandbox Image

```bash
docker build -f services/sandbox/Dockerfile --build-arg OPENCLAUDE_REF=1b7e55058cca57f2f83d7e229441631794286c1a .
```

Expected result: OpenClaude builds from the pinned SHA and all audited patches
apply cleanly.

## Patch Audit

Initial audit scope for the v0.17.1 upgrade:

| Patch file | Initial decision | Validation needed |
|---|---|---|
| `services/sandbox/patches/grep-tool-n-alias.patch` | Retain pending compatibility check | Apply against v0.17.1 and confirm grep numeric alias behavior still needs the patch. |
| `services/sandbox/patches/mcp-grpc-integration.patch` | Reconcile pending compatibility check | Compare with `multimodal-grpc-handler.patch` to avoid duplicate MCP loading behavior. |
| `services/sandbox/patches/multimodal-grpc-handler.patch` | Retain pending compatibility check | Apply against v0.17.1 and confirm gRPC handler, payload diagnostics, MCP config, cache/session behavior and permission handling still match CappyCloud contracts. |
| `services/sandbox/patches/multimodal-proto.patch` | Retain pending compatibility check | Apply against v0.17.1 and confirm proto message fields match `proto/openclaude.proto`. |
| `services/sandbox/patches/numeric-parameter-grep-guard.patch` | Reconcile pending compatibility check | Confirm whether this overlaps with `grep-tool-n-alias.patch` or wrapper behavior. |
| `services/sandbox/patches/numeric-parameter-grep-wrapper.patch` | Reconcile pending compatibility check | Confirm whether wrapper behavior is still required after upstream v0.17.1. |
| `services/sandbox/patches/read-empty-pages.patch` | Retain pending compatibility check | Apply against v0.17.1 and confirm empty page reads still need CappyCloud-specific behavior. |
| `services/sandbox/patches/worktree-tool-guard.patch` | Retain pending compatibility check | Apply against v0.17.1 and confirm worktree path guard still enforces CappyCloud isolation. |

`services/sandbox/patches/generate_patches.sh` is tooling, not an OpenClaude
runtime patch, and should be kept in sync with the final retained patch set.

Compatibility check on 2026-07-08 against upstream
`refs/tags/v0.17.1` (`1b7e55058cca57f2f83d7e229441631794286c1a`):

| Patch file | `git apply --check` | Follow-up |
|---|---:|---|
| `grep-tool-n-alias.patch` | Pass | Retain. |
| `read-empty-pages.patch` | Pass | Retain. |
| `multimodal-proto.patch` | Fail | Rebase against v0.17.1 `src/proto/openclaude.proto`. |
| `multimodal-grpc-handler.patch` | Fail | Rebase against v0.17.1 `src/grpc/server.ts`. |
| `mcp-grpc-integration.patch` | Fail | Reconcile with `multimodal-grpc-handler.patch`; do not apply both if behavior duplicates MCP loading. |
| `numeric-parameter-grep-guard.patch` | Fail | Reconcile with grep alias/wrapper behavior before adding to Dockerfile. |
| `numeric-parameter-grep-wrapper.patch` | Fail | Reconcile with grep alias/wrapper behavior before adding to Dockerfile. |
| `worktree-tool-guard.patch` | Fail | Rebase before including in Dockerfile; not currently applied by the Dockerfile patch list. |

No persistence migration is required for this feature's Spec Kit entities. They
are planning/runtime concepts, while existing migrations already cover message
payload diagnostics, conversation permission mode, and GitHub MCP seed work.

After rebasing `multimodal-proto.patch` and `multimodal-grpc-handler.patch`,
the Dockerfile patch sequence (`grep-tool-n-alias.patch`,
`multimodal-proto.patch`, `multimodal-grpc-handler.patch`,
`read-empty-pages.patch`) applies cleanly against the v0.17.1 source tree.

Sandbox build validation on 2026-07-08:

```bash
docker build -f services/sandbox/Dockerfile --build-arg OPENCLAUDE_REF=1b7e55058cca57f2f83d7e229441631794286c1a -t cappycloud-sandbox-openclaude-v0171-check .
```

Result: pass. The build fetched OpenClaude `1b7e550`, applied the Dockerfile
patch sequence, ran `bun install`, built `dist/cli.mjs` and `dist/sdk.mjs`, and
exported the local image `cappycloud-sandbox-openclaude-v0171-check:latest`.

Final sandbox build validation on 2026-07-08:

```bash
docker build -f services/sandbox/Dockerfile --build-arg OPENCLAUDE_REF=1b7e55058cca57f2f83d7e229441631794286c1a -t cappycloud-sandbox-openclaude-v0171-check .
```

Result: pass. The build fetched OpenClaude `1b7e550`, applied the retained
patch sequence, built OpenClaude v0.17.1, and exported
`cappycloud-sandbox-openclaude-v0171-check:latest`.

Focused backend validation on 2026-07-08:

```bash
C:\Users\cecon\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m pytest -o addopts='' services/api/tests/unit/test_agent_runtime_regressions.py services/api/tests/unit/test_agent_permission_mode.py
```

Result: pass, 19 tests. The local `services/api/.venv` was not usable because
its configured Python path no longer exists, so the bundled Codex Python was
used after installing `services/api/requirements.txt`.

Additional focused backend validation was attempted during US3 work. The
feature tests were added for sanitized runtime fallback metadata, authorized
final-model fallback, unauthorized fallback blocking, and provider pricing on
the final model. A temporary Python 3.12-compatible run passed 39 focused tests,
but the final repository formatting targets Python 3.14 (`target-version =
"py314"`), which uses syntax that the bundled Python 3.12 cannot parse.

Manual visual validation on 2026-07-08: not run in this implementation pass.
The required browser scenarios remain the chat event states in sections 3, 6
and 7. Current evidence covers sandbox build, patch application, and focused
backend/runtime tests only.

US2 validation notes on 2026-07-08:

- `services/api/tests/integration/test_api_conversations.py` already includes
  coverage for accepting and persisting `permission_mode` on stream requests.
- A focused unit regression now verifies distinct `GrpcSession` instances keep
  distinct `session_id` values in generated `ChatRequest`s.
- `web/src/pages/ChatPage.tsx` already clears streaming, thought, action,
  progress, activity, input and permission-warning state when switching
  conversations.
- `multimodal-grpc-handler.patch` now disables OpenClaude's in-memory
  cross-stream message cache as a visible history source; CappyCloud sends
  authorized history and owns resume state.
- Integration test execution for `test_stream_message_accepts_and_persists_permission_mode`
  was blocked by an existing import-time syntax error in a legacy repository
  mapping module.

US3 validation notes on 2026-07-08:

- `_grpc_event_handlers.py` now emits sanitized `done.fallback` metadata when
  the runtime reports a final model different from the selected model.
- `StreamMessage` rejects unauthorized final fallback models before persisting
  assistant content and keeps cost calculation tied to provider usage plus the
  catalog price of the final authorized model.
- `web/src/api.ts` parses fallback metadata through model-id and diagnostic
  text allowlists, and `ChatPage.tsx` renders a compact final-model notice.
- `AdminModelsPage.tsx`, `AdminProvidersPage.tsx`, and
  `SandboxSkillsPanel.tsx` expose catalog/provenance cues for dynamic model and
  `skill://` decisions.

## 3. Validate Conversation Source Of Truth

1. Start the API, frontend, Redis/PostgreSQL, and a sandbox.
2. Open two conversations in the same sandbox.
3. Send a message in conversation A.
4. Switch to conversation B while A has history.
5. Reload the page.
6. Return to conversation A and send a follow-up.

Expected result: messages, progress, permission mode, selected repository,
selected model, usage, and terminal state always match the active CappyCloud
conversation. No OpenClaude cache/session state appears as extra visible
history.

## 4. Validate Permission Modes

For each mode (`request_permissions`, `accept_edits`, `plan`, `auto`,
`bypass_permissions`):

1. Select the mode in the active conversation.
2. Send a request that exercises a read or tool action.
3. Confirm the stream request sends the selected mode and the UI displays the
   active mode.

Expected result: `ChatRequest.permission_mode` receives the selected value or a
documented sanitized fallback. Hard CappyCloud guardrails remain active.

## 5. Validate Fallback And Model Catalog

1. Select an authorized model and run a normal text turn.
2. Simulate or configure a provider/rate-limit fallback to another authorized
   model.
3. Simulate a fallback to a model not authorized in CappyCloud.
4. Open a conversation whose old model is retired/unavailable.

Expected result: normal turns keep the selected model; authorized fallback shows
a sanitized final-model notice and cost uses provider usage; unauthorized
fallback is blocked with an actionable error; retired models do not silently
substitute.

## 6. Validate Chat Event States

Exercise or simulate:

- normal answer;
- resumed session;
- tool start/result/error;
- action required;
- payload diagnostics;
- cancellation;
- permission warning;
- stream error;
- provider refusal;
- image/vision mismatch.

Expected result: every state is visible, non-duplicated, sanitized, and does not
expose secrets, hidden prompts, raw logs, repository file contents, or raw tool
inputs.

## 7. Validate Conversation Search

1. Search for a conversation by title.
2. Confirm filtered count and empty state.
3. Clear the search.
4. Trigger lazy loading or reload while filtered.
5. Switch conversations while the filter is active.

Expected result: filter text, count, empty result, clear action, pagination, and
active conversation state remain coherent.

## 8. Validate `skill://` Provenance

1. Register a normal repository skill and confirm it is active for the selected
   repo.
2. Expose or simulate a `skill://` runtime-discovered source.
3. Confirm it is audit-visible but inactive until CappyCloud authorizes it.

Expected result: runtime-discovered skills cannot override repository skills or
become active without registration/authorization.

## 9. Run Quality Gates

Backend:

```bash
cd services/api
ruff check .
ruff format --check .
mypy app/
pytest
```

Frontend:

```bash
pnpm --dir web lint
pnpm --dir web build
```

Expected result: gates pass, or any unavailable local tool is documented with
the equivalent Docker/CI path.

Gate results on 2026-07-08:

| Gate | Result |
|---|---|
| `python -m ruff check .` from `services/api/` | Pass. |
| `python -m ruff format --check .` from `services/api/` | Pass. |
| `python -m mypy app/` from `services/api/` | Blocked locally: bundled Python is 3.12.13, `cappycloud-api` requires Python `>=3.14`, and no Python 3.14/`uv` executable is available in PATH. |
| `python -m pytest` from `services/api/` | Blocked locally for the same Python 3.14 requirement; Python 3.12 cannot parse the repository's py314-formatted multi-exception syntax. |
| `pnpm --dir web lint` | Pass. |
| `pnpm --dir web build` | Pass, with the existing Vite warning about chunks larger than 500 kB. |
| Docker sandbox build | Pass with tag `cappycloud-sandbox-openclaude-v0171-check:latest`. |
