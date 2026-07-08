# Research: Persistent User Workspaces

## Decision: Add a per-user prepared baseline workspace

**Decision**: Maintain a persistent prepared workspace keyed by user, repository, base branch, and sandbox. This workspace is a clean baseline for repeat conversations, not the mutable task directory.

**Rationale**: The existing design creates worktrees per conversation to isolate changes. Users repeatedly selecting the same repository pay setup cost even when they only need a clean prepared baseline. A per-user baseline removes repeated setup while preserving the existing isolation boundary for edits.

**Alternatives considered**:

- Reuse the last conversation worktree directly: rejected because it can contain dirty files, partial edits, or task-specific branch state.
- Use one global repository workspace for all users: rejected because it weakens cross-user isolation.
- Create one container per user: rejected for first release because the current architecture intentionally shares sandbox containers and isolates through filesystem/worktree boundaries.

## Decision: Keep mutating flows isolated

**Decision**: Any flow that edits files, prepares diffs, pushes branches, or creates pull requests must use an isolated conversation/task workspace derived from the user's prepared baseline.

**Rationale**: Persistent baselines are valuable only if they remain clean. Mutating in place would make later conversations unpredictable and could leak changes across tabs or tasks.

**Alternatives considered**:

- Mutate the persistent workspace and reset after completion: rejected because failures, interrupts, and concurrent runs make reset semantics risky.
- Ask the user every time whether to isolate: rejected for first release because safety should be default and the existing product already treats edits as isolated.

## Decision: Store workspace lifecycle in the API database

**Decision**: Store ownership, repository, base branch, sandbox, path, status, health timestamps, and last-use metadata in the database.

**Rationale**: The API already owns user/repository authorization and conversation metadata. Persisting workspace registry there enables authorization checks, cleanup, repair, and audit without relying on filesystem discovery alone.

**Alternatives considered**:

- Store only marker files in the sandbox volume: rejected because authorization, cleanup, and cross-sandbox routing need database-level visibility.
- Store only in Redis: rejected because persistent workspaces must survive API restarts and Redis eviction.

## Decision: Use sandbox sidecar for filesystem and Git operations

**Decision**: Continue routing workspace creation, health checks, repair, and cleanup through the sandbox session server.

**Rationale**: ADR-002 requires the API not to manipulate sandbox files directly. The session server already owns worktree creation and path validation inside `/repos`.

**Alternatives considered**:

- Let the API run Git commands directly: rejected by architecture and isolation rules.
- Let the agent create workspaces lazily through shell tools: rejected because workspace lifecycle must be deterministic before the model acts.

## Decision: Cleanup is operational, not user-facing in v1

**Decision**: Provide cleanup for stale persistent workspaces by status/age, but do not require a dedicated user UI in the first release.

**Rationale**: The immediate user value is faster repeat conversations. Cleanup can initially be automatic/admin-operational as long as it never deletes active conversation workspaces.

**Alternatives considered**:

- Build user-facing workspace management UI now: deferred to keep the first release scoped.
- Never clean persistent workspaces: rejected because shared sandbox volumes need bounded growth.
