# Contract: Sandbox Session Server Workspace Operations

The API must continue to use the sandbox sidecar for filesystem and Git operations.

## Ensure User Workspace

```http
POST /user-workspaces/ensure
Content-Type: application/json
```

```json
{
  "workspace_id": "uuid",
  "user_key": "stable-user-key",
  "repo": {
    "slug": "Seller",
    "alias": "Seller",
    "base_branch": "main",
    "clone_url": "https://example/repo.git"
  },
  "workspace_path": "/repos/users/<user-key>/Seller/main"
}
```

### Response

```json
{
  "workspace_id": "uuid",
  "workspace_path": "/repos/users/<user-key>/Seller/main",
  "status": "ready",
  "created": false,
  "clean": true,
  "message": "Workspace ready."
}
```

### Required Behavior

- Must reject paths outside the user workspace root.
- Must create or repair the workspace idempotently.
- Must repair a workspace that contains unexpected local changes by discarding uncommitted baseline changes before reporting it as clean.
- Must return enough health detail for the API to mark `ready`, `dirty`, `missing`, or `error`.

## Create Conversation Workspace From User Baseline

```http
POST /sessions
Content-Type: application/json
```

The existing session creation endpoint may receive source workspace metadata per repository:

```json
{
  "session_id": "abc123",
  "session_root": "/repos/sessions/abc123",
  "repos": [
    {
      "slug": "Seller",
      "alias": "Seller",
      "base_branch": "main",
      "branch_name": "cappy/Seller/abc123-Seller",
      "worktree_path": "/repos/sessions/abc123/Seller",
      "source_workspace_path": "/repos/users/<user-key>/Seller/main"
    }
  ]
}
```

### Required Behavior

- Read-only conversations may use the prepared workspace as context only when no mutation can occur.
- Mutating conversations must receive an isolated worktree path.
- If `source_workspace_path` is provided, session creation should derive from that prepared baseline when safe.
- Existing path guards for `/repos/sessions/` remain in force for conversation workspaces.
