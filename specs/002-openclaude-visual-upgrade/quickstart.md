# Quickstart: Validate OpenClaude v0.14.0 Chat Visual Upgrade

This guide is for validating the implementation after tasks are generated and
executed. It does not deploy production containers.

## Prerequisites

- PostgreSQL and Redis available for the API test/dev stack.
- Python API dependencies installed.
- Web dependencies installed with the package manager recorded in
  `web/package.json`.
- Docker available if validating the sandbox image.

## Backend Validation

```bash
cd services/api
pip install -r requirements.txt -e ".[dev]"
alembic upgrade head
ruff check .
ruff format --check .
mypy app/
pytest
```

Expected outcomes:

- Message domain/entity/repository tests pass with `payload_diagnostics`.
- Adapter contract tests pass for both in-memory and SQLAlchemy message
  repositories.
- Conversation streaming tests prove a `payload_diagnostic` event is captured,
  sanitized, persisted with the assistant message, and returned by message
  history.
- Existing tests for no-diagnostic turns still pass without empty metadata.

## Frontend Validation

```bash
pnpm --dir web install
pnpm --dir web lint
pnpm --dir web build
```

Expected outcomes:

- `ChatMessage` accepts optional `payload_diagnostics`.
- Diagnostic-enabled messages render a compact summary with total size and the
  three largest safe categories.
- Expanding the summary shows all safe categories.
- Messages without diagnostics render exactly as before.

## Sandbox Runtime Validation

Build the sandbox image with the v0.14.0 ref before deploying it anywhere:

```bash
docker build -f services/sandbox/Dockerfile \
  --build-arg OPENCLAUDE_REF=66ed9b61dcefea4bd58d1c24011cf32015b0fb29 \
  .
```

Expected outcomes:

- The image builds successfully.
- Each local OpenClaude patch is either applied, removed because upstreamed, or
  adjusted intentionally.
- Existing CappyCloud-specific behavior remains available: multimodal request
  support, dynamic model/provider routing, MCP integration, worktree guard, and
  tool parameter guards when still needed.

## Manual Chat Scenarios

1. Diagnostic-enabled turn:
   - Send a message with enough history/context or attachments to produce
     diagnostics.
   - Confirm the chat shows a compact diagnostic summary.
   - Confirm the largest category is identifiable in under 10 seconds.
   - Reload the conversation and confirm the same summary remains visible.

2. No diagnostic turn:
   - Send a normal short message.
   - Confirm no diagnostic placeholder or empty container appears.

3. Safety check:
   - Use a prompt with repository context and attachments.
   - Confirm the diagnostic displays only category labels and numeric sizes.
   - Confirm no raw prompt, hidden instruction, filename, path, provider key, or
     binary content is visible.

4. Existing visual regressions:
   - Trigger or simulate a tool error with stdout.
   - Trigger or simulate timeout handling.
   - Trigger or simulate an action-required prompt.
   - Confirm each state uses the existing visual treatment and does not create
     duplicate or stuck UI.
   - Confirm the spinner clears after `done`, `error`, abort, or timeout.
   - Confirm resume/thinking activity remains attached to the originating user
     turn and is not replayed as a new assistant answer.

## Final Visual Scope Notes

- Only request payload diagnostics add a new chat surface.
- The compact diagnostic summary shows total payload bytes and up to three
  largest safe categories.
- Expanded diagnostics show the same safe categories sorted by size.
- Provider/OAuth/authentication changes do not add chat controls; their final
  failures remain normal assistant error events.
- OpenClaude TUI-only fixes, XML serialization, stdin/raw-mode fixes, and
  retry internals remain outside CappyCloud chat UI scope.

## Validation Log

- Patch application against OpenClaude `66ed9b61dcefea4bd58d1c24011cf32015b0fb29`
  passed for the Dockerfile patch order.
- Backend gates passed with Python 3.14 venv: `ruff check .`,
  `ruff format --check .`, `mypy app/`, and full `pytest` with 581 tests and
  80.28% coverage.
- Focused backend tests also passed with Python 3.14 venv:
  `pytest --no-cov tests/unit/use_cases/test_conversation_streaming.py tests/adapter/test_sqlalchemy_sandbox_message_repos.py tests/integration/test_api_conversations.py tests/unit/test_agent_runtime_regressions.py`.
- Frontend `pnpm lint` and `pnpm build` passed.
- Docker sandbox image build passed with tag
  `cappycloud-sandbox:openclaude-v014-test`.
- Local Docker Compose rebuild/recreate passed for `sandbox`, `api`, and `web`.
  The running sandbox reported OpenClaude `0.14.0`, API and web healthchecks
  returned `{"status":"ok"}`, and API-to-sandbox gRPC readiness passed.
- Real local chat smoke via Docker API/SSE passed: the stream emitted
  `payload_diagnostic`, assistant text, and `done`; the persisted assistant
  message kept the diagnostic breakdown, while the user message stored SQL NULL
  for `payload_diagnostics`.
- Manual browser preview passed against `http://localhost:8013/chat`: the chat
  displayed the compact `Pedido` summary with total size and top categories, and
  the expanded panel showed all safe categories with bars and byte/percentage
  values. Temporary preview users/conversations were removed after validation.
- Backend/frontend security review confirmed diagnostics expose only allowlisted
  category keys, canonical labels, byte counts, percentages, source allowlist
  and safe timestamp text. Raw labels, file paths, prompts, provider keys and
  binary payload fields are dropped.

## Validation Gaps

- No remaining validation gap for the new diagnostic visual. Existing
  tool/action/error/timeout states are covered by the stream, agent runtime, and
  API regression tests listed above.

## Done Criteria

- Backend and frontend gates pass or blockers are documented.
- Sandbox image builds with the pinned OpenClaude v0.14.0 commit.
- Diagnostic persistence and reload behavior are verified.
- No production deploy, image push, or container rollout is performed unless
  requested separately.
