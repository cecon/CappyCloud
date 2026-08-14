# Validation Notes: OpenClaude 0.27.0 Upgrade

## Environment

- Date: 2026-08-07
- Scope: local validation only
- Production deployment: not executed

## Static Evidence

- OpenClaude git tags re-checked with `git ls-remote --tags`.
- npm metadata re-checked with `npm view @gitlawb/openclaude version dist-tags.latest --json`.
- Target remains `0.27.0`.

## Automated Gates

- Frontend focused parsing test passed:
  `pnpm test -- --run src/api.test.ts`.
- Frontend focused runtime UI tests passed:
  `pnpm test -- --run src/api.test.ts src/components/chat/AgentActivityCard.test.tsx src/components/MessageTimeline.test.tsx`
  -> `3 passed`, `7 passed`.
- Frontend focused provider/model tests passed:
  `pnpm test -- --run src/pages/AdminProvidersPage.test.tsx src/components/ModelPicker.test.tsx`
  -> `2 passed`, `4 passed`.
- Frontend branding/menu exclusion tests passed:
  `pnpm test -- --run src/components/layout/BrandMark.test.tsx src/components/layout/routeCoverage.test.ts`
  -> `2 passed`, `2 passed`.
- Frontend lint passed: `pnpm lint`.
- Frontend build passed: `pnpm build`.
- Frontend full test suite passed:
  `pnpm test` -> `7 passed`, `14 passed`.
- API venv was repaired with `uv`; runtime dependencies from `requirements.txt`
  were installed into `.venv`.
- API focused tests passed:
  `uv run --extra dev pytest tests/unit/test_agent_runtime_regressions.py tests/unit/test_openclaude_upgrade_readiness.py -q --no-cov`
  -> `20 passed`.
- API focused runtime and streaming tests passed:
  `uv run --extra dev pytest tests/unit/test_agent_runtime_regressions.py tests/unit/use_cases/test_conversation_streaming.py -q --no-cov`
  -> `32 passed`.
- API focused provider auth tests passed:
  `uv run --extra dev pytest tests/unit/use_cases/test_admin_ai_provider_auth.py tests/unit/use_cases/test_admin_ai_catalog_helpers.py tests/integration/test_api_admin_ai_catalog.py -q --no-cov`
  -> `12 passed`.
- API conversation regression tests passed after type-only router fix:
  `uv run --extra dev pytest tests/unit/use_cases/test_conversation_streaming.py tests/integration/test_api_conversations.py -q --no-cov`
  -> `22 passed`.
- API full pytest without coverage passed:
  `uv run --extra dev pytest -q --no-cov`
  -> `561 passed`, `3 skipped`.
- API mypy passed:
  `uv run mypy app/` -> `Success: no issues found in 162 source files`.
- Python full lint/format passed:
  `uv run ruff check .` and `uv run ruff format --check .`.
- Initial `uv run ruff ...` from repository root failed because `ruff` was not
  installed in that root environment. Re-running from `services/api/`, where
  the project dev environment is configured, passed for the touched files.
- The same focused API selection without `--no-cov` executed 20 passing tests
  but failed the repository-wide 80% coverage gate because it intentionally ran
  only two files. Full `pytest` remains pending.

## Sandbox Build

- Patch compatibility checked against OpenClaude
  `7eeb90fb5bc970776e8f8acef2a2d41ff457865f` with `git apply --check`.
  All Dockerfile-applied patches passed.
- Local sandbox image build passed:
  `docker build -f services/sandbox/Dockerfile -t cappycloud-sandbox-openclaude-v0270-check .`.
- Container version validation passed:
  `docker run --rm --entrypoint sh cappycloud-sandbox-openclaude-v0270-check -lc "node /openclaude/dist/cli.mjs --version"`
  -> `0.27.0 (OpenClaude)`.
- Short entrypoint validation passed: a detached container stayed running after
  startup and logged `gRPC Server running at 0.0.0.0:50051`.
- During sandbox validation, an initial runtime SyntaxError in the numeric
  parameter regex and a duplicate permission-decision declaration were found
  and fixed before the final successful build.

## Local Stack

`docker compose up -d --build` was not executed in this implementation pass.
Sandbox image build and entrypoint validation were executed locally.

## Manual Scenarios

- Long-running/stalled behavior: covered by backend stream heartbeat tests and
  frontend runtime-state rendering tests. Full local stack scenario remains
  pending.
- Permission timeout/canceled/failed/done labels: covered by frontend parser
  and `AgentActivityCard` tests.
- Subagent grouping: covered by backend normalization tests, conversation
  stream pass-through tests, frontend API parser tests, and activity card tests.
- Context progress: covered by backend normalization tests, conversation stream
  pass-through tests, frontend API parser tests, context bar rendering support,
  and timeline tests proving it does not appear as usage/cost.
- Conversation switch isolation: `ChatPage` clears context, subagent, and
  runtime-state arrays on conversation switch and before a new non-resume send.
  Browser/manual verification in the full local stack remains pending.
- Admin provider auth visibility: provider auth state is derived by
  `DeriveProviderAuthState` and exposed only through admin provider DTO fields.
  Regular user model/provider DTOs remain unchanged and do not include auth
  state fields.
- Branding/menu exclusion: authenticated brand and navigation tests assert no
  upstream OpenClaude, buddy, or terminal-only copy appears in product surfaces.

## Security Review Notes

- Focused review of changed files did not find hardcoded production secrets,
  new `dangerouslySetInnerHTML`, `eval`, `os.system`, `subprocess` shell use or
  raw secret logging.
- Token/secret matches in changed scope are existing API parameter names,
  documentation rollback criteria, or tests that assert sanitization of
  synthetic secret-looking strings.
- Security review found a pre-existing Git provider token update that sent the
  PAT in the URL query string. It was changed to a JSON request body and locked
  with a frontend regression test so reusable credentials are not exposed in
  browser history or access logs.
