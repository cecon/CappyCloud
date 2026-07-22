# Quickstart: Project-Aware Chat Suggestions

## Prerequisites

- Backend dependencies installed in `services/api`.
- Frontend dependencies installed in `web`.
- Test database/migrations available as in the normal CappyCloud development flow.
- At least one active repository visible to the test user.

## Backend Validation

1. Run API quality gates:

   ```bash
   cd services/api
   ruff check .
   ruff format --check .
   mypy app/
   pytest
   ```

2. Validate migration applies cleanly:

   ```bash
   cd services/api
   alembic upgrade head
   ```

3. Seed or create a repository with documents/skills, then request suggestions:

   ```bash
   curl -H "Authorization: Bearer <token>" \
     "http://localhost:8000/api/project-suggestions?repo_slug=<repo-slug>"
   ```

   Expected result: HTTP 200 with `cards` containing 3 to 4 safe Portuguese prompts when enough active suggestions exist, or project-aware initial suggestions when history is not calibrated.

4. Validate access control:

   ```bash
   curl -H "Authorization: Bearer <other-user-token>" \
     "http://localhost:8000/api/project-suggestions?repo_slug=<restricted-repo-slug>"
   ```

   Expected result: HTTP 403 or 404-style concealment according to existing repository access behavior; no suggestions from restricted projects are returned.

5. Trigger recalibration as an admin:

   ```bash
   curl -X POST -H "Authorization: Bearer <admin-token>" \
     -H "Content-Type: application/json" \
     -d '{"trigger":"manual","force":false}' \
     "http://localhost:8000/api/project-suggestions/<repository-id>/recalibrate"
   ```

   Expected result: HTTP 202 with a queued or created calibration run.

## Frontend Validation

1. Run frontend gates:

   ```bash
   cd web
   pnpm lint
   pnpm build
   ```

2. Start the app in the normal development environment.

3. Open the chat initial state with no messages.

4. Select project A.

   Expected result: heading/supporting copy and 3 to 4 cards reflect project A; composer, attachments, branch, model, and permission controls remain usable.

5. Select project B.

   Expected result: cards and contextual copy update to project B without page reload and without showing project A cards.

6. Click a suggestion card.

   Expected result: the card prompt fills the composer text only; selected project, branch, sandbox, model, permission mode, and attachments are preserved.

7. Test unavailable/empty states.

   Expected result: no overlapping UI, no empty card shells, and user-facing Portuguese feedback or safe fallback when suggestions cannot load.

8. Open an existing conversation with message history.

   Expected result: initial project suggestion cards are not rendered inside the active conversation history.

9. Switch between two projects while timing suggestion load.

   Expected result: visible cards update within 2 seconds in normal development smoke checks.

## Privacy Validation

- Create user messages with sensitive-looking values such as API keys, customer names, incident identifiers, and file paths.
- Run recalibration.
- Confirm generated suggestions and operational status do not expose raw prompts, authors, conversation IDs, secrets, or sensitive snippets.

## Scheduler Validation

- Confirm the API registers a daily project-suggestion recalibration job on startup.
- Update or ingest a project document/skill.
- Confirm the project receives a queued/debounced recalibration without waiting solely for the next daily cycle.

## Local Validation Notes

- Passed: `services/api/.venv/Scripts/ruff.exe check app tests`.
- Passed: `services/api/.venv/Scripts/ruff.exe format --check app tests`.
- Passed: `pnpm --dir web lint`.
- Passed: `pnpm --dir web build`.
- Passed: Python syntax compilation with the bundled Codex Python runtime.
- Not run locally: `alembic revision`/`alembic upgrade head`, `mypy app`, and `pytest`.
  The local `services/api/.venv` executable points to a removed Python path:
  `C:\Users\cecon\AppData\Roaming\uv\python\cpython-3.14.3-windows-x86_64-none\python.exe`.
  The bundled Codex Python runtime does not include `pytest` or a runnable Alembic CLI.
