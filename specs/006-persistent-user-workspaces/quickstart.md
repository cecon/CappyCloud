# Quickstart: Persistent User Workspaces

## Prerequisites

- Docker Compose stack is running.
- At least one active repository is configured and accessible to the test user.
- The test user has access to that repository and at least one active text model.

## Validation Scenario 1: First Conversation Prepares Workspace

1. Start a new conversation as User A with repository `Seller` and base branch `main`.
2. Send a simple read-only prompt.
3. Observe session status.

Expected result:

- A user workspace registry entry exists for User A, `Seller`, and `main`.
- The first run may show workspace creation/preparation.
- The conversation reaches agent response state normally.

## Validation Scenario 2: Second Conversation Reuses Workspace

1. As the same User A, start a second new conversation with `Seller` and `main`.
2. Send a simple read-only prompt.

Expected result:

- The system reports workspace reuse or skips full workspace preparation.
- The second preparation is visibly faster than the first.
- The same user workspace registry entry is updated with a newer `last_used_at`.

## Validation Scenario 3: Cross-User Isolation

1. As User A, create or reuse a workspace for `Seller`.
2. As User B, who also has access to `Seller`, start a conversation for `Seller`.
3. Compare the recorded workspace entries and paths.

Expected result:

- User A and User B have distinct workspace records and paths.
- User B cannot observe User A's uncommitted files or workspace path contents.

## Validation Scenario 4: Mutating Conversation Isolation

1. As User A, start two conversations for `Seller`.
2. In conversation 1, ask the agent to make a small file edit.
3. In conversation 2, ask for repository status or file contents.

Expected result:

- Conversation 1 uses an isolated mutating workspace.
- Conversation 2 does not see conversation 1's uncommitted changes.
- The persistent user baseline remains clean.

## Validation Scenario 5: Repair Missing Workspace

1. Delete the user workspace path from the sandbox volume.
2. Keep the database registry row.
3. Start another conversation for the same user/repository/base branch.

Expected result:

- The system detects the missing workspace.
- The workspace is recreated or repaired automatically.
- The user receives a normal agent response without manual cleanup.

## Required Gates

Run the relevant checks before marking implementation complete:

```powershell
docker compose run --rm --no-deps -v "D:/projetos/CappyCloud/services/api:/app" api python -m compileall -q app
npm --prefix web run lint -- --max-warnings=0
docker compose build api web sandbox
docker compose up -d --no-deps --force-recreate api web sandbox
```

When dev dependencies are available, also run:

```powershell
cd services/api
ruff check .
ruff format --check .
mypy app/
pytest
```
