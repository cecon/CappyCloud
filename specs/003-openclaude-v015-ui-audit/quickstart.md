# Quickstart: Validate OpenClaude v0.15.0 Permission Mode Upgrade

## Prerequisites

- Backend dependencies installed for `services/api`.
- Frontend dependencies installed under `web/`.
- Docker available for sandbox image validation.
- OpenClaude tag `v0.15.0` reachable from
  `https://github.com/Gitlawb/openclaude.git`.

## Implementation setup notes

- Current sandbox pin before this upgrade:
  `services/sandbox/Dockerfile` uses
  `OPENCLAUDE_REF=66ed9b61dcefea4bd58d1c24011cf32015b0fb29`.
- Verified target on 2026-06-17:
  `refs/tags/v0.15.0` resolves to
  `670744fc70353f2270e86531dffa1c06f4fac79c`.
- Chat UI control patterns reviewed in `web/src/pages/ChatPage.tsx` and
  `web/src/components/chat.module.css`; the selector should use the existing
  compact toolbar/control style.

## Local patch audit checklist

Record the final status for every local OpenClaude patch before marking the
runtime upgrade complete:

| Patch | v0.15.0 status |
|---|---|
| `auto-approve-tools.patch` | Removed as obsolete; request-scoped permission behavior moved into `multimodal-grpc-handler.patch`. |
| `grep-tool-n-alias.patch` | Retained unchanged; applies to v0.15.0. |
| `mcp-grpc-integration.patch` | Not applied by current Dockerfile; fails standalone v0.15.0 apply check and remains pending/unused unless reintroduced. |
| `multimodal-grpc-handler.patch` | Changed for v0.15.0; applies cleanly and maps all five request-scoped permission modes. |
| `multimodal-proto.patch` | Changed for v0.15.0; applies cleanly and adds `permission_mode = 11`. |
| `numeric-parameter-grep-guard.patch` | Not applied by current Dockerfile; fails standalone v0.15.0 apply check and remains pending/unused unless reintroduced. |
| `numeric-parameter-grep-wrapper.patch` | Not applied by current Dockerfile; fails standalone v0.15.0 apply check and remains pending/unused unless reintroduced. |
| `read-empty-pages.patch` | Retained unchanged; applies to v0.15.0. |
| `worktree-tool-guard.patch` | Not applied by current Dockerfile; fails standalone v0.15.0 apply check and remains pending/unused unless reintroduced. |

## Backend validation

```bash
cd services/api
ruff check .
ruff format --check .
mypy app/
pytest
```

Expected outcomes:

- New conversations default to `permission_mode=request_permissions`.
- Stream requests accept all five allowed modes and reject unknown values.
- Stream requests persist the resolved mode on the conversation before
  dispatching the agent.
- The pipeline body contains `permission_mode`.
- Authorization behavior for conversations, sandboxes, repositories,
  attachments, and models is unchanged.

## Frontend validation

```bash
cd web
npm run lint
npm run build
```

Manual browser scenarios:

1. Open a new chat.
2. Confirm the permission selector is visible before the first message and
   defaults to "Solicitar permissoes".
3. Select "Aceitar edicoes"; confirm a lower-severity caution appears.
4. Select "Modo automatico"; confirm a high-risk bypass warning appears.
5. Select "Ignorar permissoes"; confirm the same high-risk bypass warning
   appears.
6. Select "Modo de planejamento"; confirm the high-risk bypass warning is not
   shown.
7. Trigger or simulate sanitized `status.metadata.permission_warning` runtime
   context and confirm the warning indicates runtime confirmation without raw
   logs, provider keys, hidden prompts, repository contents, or tool inputs.
8. Send a message, reload the page, and confirm the conversation shows the last
   selected mode.
9. Change mode mid-conversation and confirm only the next execution uses the
   new mode.

Existing chat-state regression scenarios:

1. Send a normal prompt and confirm the assistant answer, model label, tokens,
   and cost render as before.
2. Trigger a tool call and confirm `tool_start`, tool result, and any recovered
   arguments remain visible in the activity timeline.
3. Trigger an `ActionRequired` prompt with `request_permissions`; answer it and
   confirm the stream resumes.
4. Trigger a tool error and confirm the error state stays attached to the tool
   activity, not to the permission selector.
5. Cancel an active run and confirm the interrupted message appears once, the
   stop timer clears, and the selector is enabled again.
6. Force an agent/provider error and confirm the sanitized message is shown
   without raw provider payloads, keys, hidden prompts, repository contents, or
   tool inputs.
7. Confirm payload diagnostics still expand/collapse and still show sanitized
   category labels.

## Agent/runtime validation

`proto/openclaude.proto` is the canonical repository contract. Generated
Python/Node stubs are produced inside the sandbox/OpenClaude build path; if a
local generated stub is introduced later, regenerate it from the updated proto
before running the gates.

Build the sandbox image with the v0.15.0 tag SHA:

```bash
docker build -f services/sandbox/Dockerfile `
  --build-arg OPENCLAUDE_REF=670744fc70353f2270e86531dffa1c06f4fac79c `
  -t cappycloud-sandbox:openclaude-v015-test .
```

Build result recorded on 2026-06-17:

- Command completed successfully from `D:\projetos\CappyCloud`.
- The OpenClaude build reported version `0.15.0`.
- Image tag created: `docker.io/library/cappycloud-sandbox:openclaude-v015-test`.
- Final image manifest list digest:
  `sha256:6ebbbf4719908b8c01acb4b39bca099a0f9033e794625b1c39c5a5352608dcc6`.

Expected outcomes:

- The sandbox image builds from the pinned OpenClaude revision.
- Local patches either apply cleanly or are documented as changed, removed, or
  obsolete.
- `request_permissions` still produces `ActionRequired` when OpenClaude needs
  approval.
- `accept_edits` allows edit actions inside CappyCloud hard boundaries but does
  not bypass all prompts.
- `plan` does not perform mutating actions.
- `auto` and `bypass_permissions` bypass OpenClaude permission prompts while
  CappyCloud hard boundaries still block out-of-scope actions.
- When the OpenClaude startup warning is safely detected, the agent emits
  sanitized `status.metadata.permission_warning.runtime_confirmed=true`.
- Tool arguments recovered via v0.15.0 stream behavior still appear in the
  existing tool activity UI.

Legacy parameter cleanup:

- `services/sandbox/env_init.sh` must not default or export a process-wide
  permissive auto-approval mode.
- `services/sandbox/patches/auto-approve-tools.patch` was removed because its
  process-wide env-only behavior is obsolete.
- `services/sandbox/patches/generate_patches.sh` must not regenerate the old
  env-only auto-approval patch.
- Active runtime paths should have no remaining legacy global parameter that can
  override `permission_mode`.

Cleanup result recorded on 2026-06-17:

- `rg "OPENCLAUDE_AUTO_APPROVE|auto-approve-tools" -n services/sandbox services/api services/cappycloud_agent web docs specs/003-openclaude-v015-ui-audit`
  returns only Spec Kit documentation references, not active runtime code.
- `git status --short` shows no tracked build output or temporary workspace
  artifacts created by the sandbox/frontend/backend validation commands.

Sandbox patch validation notes:

- Local patch apply check on 2026-06-17 against
  `670744fc70353f2270e86531dffa1c06f4fac79c` passed for Dockerfile-applied
  patches in order after CRLF normalization:
  `grep-tool-n-alias.patch`, `multimodal-proto.patch`,
  `multimodal-grpc-handler.patch`, `read-empty-pages.patch`.
- `request_permissions` leaves OpenClaude's normal prompt flow active.
- `accept_edits` auto-allows edit tools (`Write`, `Edit`, `NotebookEdit`,
  `MultiEdit`) after the `tool_start` event and before `ActionRequired`.
- `plan` denies mutating tools (`Write`, `Edit`, `NotebookEdit`, `MultiEdit`,
  `Bash`) and leaves read-only tools on the normal flow.
- `auto` and `bypass_permissions` auto-allow OpenClaude permission prompts after
  the `tool_start` event while the CappyCloud worktree guard still runs first.
- `OPENCLAUDE_AUTO_APPROVE` has no remaining active reference under
  `services/sandbox`.

Watcher reload burst validation:

- Change or reload sandbox skills/settings rapidly and confirm the chat/admin UI
  does not duplicate status rows, flicker conversation selection, or spawn
  duplicate active agent states.
- OpenClaude v0.15.0 watcher debounce is treated as runtime behavior; CappyCloud
  should only surface stable status events through the existing SSE stream.

## Gate execution record

Automated gates executed on 2026-06-17:

- `services/api`: `ruff check .` passed.
- `services/api`: `ruff format --check .` passed.
- `services/api`: `mypy app/` passed.
- `services/api`: full `pytest` passed with 604 tests and 80.41% coverage.
- `web`: `npm run lint` passed.
- `web`: `npm run build` passed. Vite reported only chunk-size/plugin timing
  warnings.
- Repository-targeted regression run passed for permission mode, payload
  diagnostics, stream helpers, conversation streaming, agent permission mode,
  runtime regressions, and conversation integration tests.

Manual scenario execution note:

- The browser scenarios above remain the operational acceptance checklist for a
  running CappyCloud stack with a live sandbox session.
- This Codex run did not start the full interactive app stack or perform live
  browser/sandbox chat execution, so no runtime-only manual pass is claimed.
- No additional residual code risk was found by the automated gates, sandbox
  image build, legacy-parameter cleanup check, code review, or vulnerability
  review.

## Release item UI-scope review

Review the matrix in [spec.md](spec.md):

- Every v0.15.0 release item has one UI decision.
- The safety item maps to the chat-level permission selector.
- Provider classification is not used for warning severity.
- OpenClaude terminal-menu-only features remain outside CappyCloud chat unless
  a future spec exposes them through the CappyCloud session flow.

## Out of scope

- Production deployment or Portainer/Swarm rollout.
- Automatic image push.
- New provider onboarding UI.
- Redesigning the v0.14.0 payload diagnostics UI.
