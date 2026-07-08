# Data Model: Persistent User Workspaces

## UserRepositoryWorkspace

Represents a persistent prepared baseline workspace for one user, repository, base branch, and sandbox.

### Fields

- `id`: Stable identifier.
- `user_id`: Owner user.
- `repository_id`: Repository catalog entry.
- `sandbox_id`: Sandbox where the workspace is materialized.
- `base_branch`: Selected base branch used to prepare the workspace.
- `workspace_path`: Absolute path inside the sandbox volume.
- `status`: Lifecycle state.
- `health_message`: Optional diagnostic for repair/error states.
- `last_prepared_at`: When the workspace was last created or repaired.
- `last_used_at`: When a conversation last reused the workspace.
- `created_at`: Creation timestamp.
- `updated_at`: Last registry update timestamp.

### Uniqueness

- One active registry row per `(user_id, repository_id, sandbox_id, base_branch)`.

### States

- `preparing`: Creation is in progress.
- `ready`: Baseline exists and is safe to reuse.
- `repairing`: Recorded workspace is missing/unhealthy and is being repaired.
- `dirty`: Baseline contains unexpected local changes and must be repaired before reuse.
- `missing`: Registry exists but filesystem path is absent.
- `unauthorized`: User no longer has repository access.
- `error`: Last preparation or repair failed.

### Validation Rules

- `workspace_path` must resolve under the sandbox user workspace root.
- `base_branch` must be non-empty and match the selected repository branch.
- A workspace cannot transition to `ready` unless the sandbox reports it exists and is clean.
- A dirty baseline must be repaired by discarding uncommitted baseline changes before reuse.
- A workspace cannot be reused when user repository access is missing.

## Conversation Workspace

Represents an isolated workspace for a conversation or task when mutation safety is required.

### Fields

- `conversation_id`: Conversation that owns the isolated workspace.
- `source_workspace_id`: Optional user baseline from which it was derived.
- `repository_id`: Repository catalog entry.
- `branch_name`: Isolated branch name.
- `worktree_path`: Existing per-conversation path used by the agent.
- `mode`: `read_only`, `mutating`, or `pr`.

### Validation Rules

- Mutating and PR flows must use isolated conversation workspaces.
- Conversation workspaces remain owned by the conversation and are cleaned by existing session cleanup rules.

## WorkspaceHealthCheck

Represents the result of checking a user workspace in the sandbox.

### Fields

- `workspace_id`: User workspace being checked.
- `exists`: Whether the filesystem path exists.
- `clean`: Whether the baseline has no unexpected local changes.
- `current_branch`: Observed branch/ref.
- `message`: Human-readable diagnostic.
- `checked_at`: Check timestamp.

## Relationships

- User 1 -> many UserRepositoryWorkspace.
- Repository 1 -> many UserRepositoryWorkspace.
- Sandbox 1 -> many UserRepositoryWorkspace.
- UserRepositoryWorkspace 1 -> many Conversation Workspace derivations over time.
