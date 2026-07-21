# Quickstart: OpenClaude v0.24 Chat Commands

## Prerequisites

- Docker available for sandbox build.
- Backend dependencies installed for `services/api`.
- Frontend dependencies installed for `web`.
- Access to GitHub network for OpenClaude tag verification.

## 1. Verify Release Target

```powershell
git ls-remote --tags https://github.com/Gitlawb/openclaude.git refs/tags/v0.24.0
```

Expected:

```text
2ff93a10bf88ab6d7030fc4ade5316a7424fa2f9 refs/tags/v0.24.0
```

Observed on 2026-07-21:

```text
2ff93a10bf88ab6d7030fc4ade5316a7424fa2f9 refs/tags/v0.24.0
```

## 2. Audit Current Runtime Pin

```powershell
rg -n "OPENCLAUDE_REF|git apply|perl -0pi" services/sandbox/Dockerfile services/sandbox/env_init.sh services/sandbox/patches
```

Expected:

- Current pin is identified before update.
- Every local patch and inline edit is listed for classification.

## 3. Backend Gates

```powershell
cd services/api
ruff check .
ruff format --check .
mypy app/
pytest
```

Expected:

- All pass, or local environment blockers are recorded with exact error.

## 4. Frontend Gates

```powershell
cd web
pnpm run lint
pnpm run build
```

Expected:

- Chat composer and command UI compile and lint.

Observed on 2026-07-21:

- `pnpm run lint`: pass.
- `pnpm run build`: pass.

## 5. Sandbox Build

```powershell
docker build `
  --build-arg OPENCLAUDE_REF=2ff93a10bf88ab6d7030fc4ade5316a7424fa2f9 `
  -f services/sandbox/Dockerfile `
  -t cappycloud-sandbox:openclaude-v024-check .
```

Expected:

- Image builds successfully.
- Patch audit notes identify retained, changed, removed or obsolete local changes.

Observed on 2026-07-21:

- Image built successfully as `cappycloud-sandbox:openclaude-v024-check`.
- Runtime smoke returned `/runtime/status` as `{"openclaude":"running","grpc_port":50051}`.
- `/health` returned `{"status":"ok","openclaude":"running","sessions":0}`.
- Startup logs included `gRPC Server running at 0.0.0.0:50051`.
- `multimodal-grpc-handler.patch` still produced rejects tolerated by the current Dockerfile; see `runtime-audit.md` before production rollout.

## Command Catalog Seed

The checked-in v0.24 fallback catalog lives at `services/sandbox/openclaude-v024-commands.json`.
Initial commands:

- `/model`
- `/ctx`
- `/cost`
- `/doctor`
- `/bughunter`
- `/bughunter-security`
- `/bughunter-perf`
- `/set-context-window`
- `/clear-context-window`
- `/goal`
- `/update`

## 6. Manual Chat Validation

Run the app stack and open an authenticated chat.

Scenarios:

1. Type `/` in an empty composer.
   - Expected: command suggestions open within 2 seconds.
2. Type `/mod`.
   - Expected: list filters to matching commands such as `/model`.
3. Type ordinary prose with a URL or path containing `/`.
   - Expected: suggestions do not interrupt normal typing.
4. Select an unavailable terminal-only command.
   - Expected: Portuguese unavailable reason appears and command does not execute.
5. Execute a read-only diagnostic command.
   - Expected: timeline shows command start and sanitized result.
6. Execute a command that changes model/context/runtime/session/external access.
   - Expected: inline confirmation appears before execution.
7. Keep an action-required prompt pending and open `/`.
   - Expected: prompt and pending reply are preserved.
8. Attach an image or document and open slash suggestions.
   - Expected: attachment tray and draft state remain intact.
9. Trigger a normal agent response.
   - Expected: text, tool events, done event, model, tokens and cost still render correctly.
10. Cancel a running turn.
   - Expected: cancellation state remains clear and command UI recovers.

## 7. Contract Review

Review:

- [API contract](contracts/api-contract.md)
- [Runtime contract](contracts/runtime-contract.md)
- [UI contract](contracts/ui-contract.md)
- [Data model](data-model.md)

Expected:

- Every command family in the spec has an availability/authorization decision.
- Every new event/state has a validation scenario.
