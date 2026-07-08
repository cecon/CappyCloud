# Contract: User Workspace API

This contract documents the internal API behavior expected between the browser/API use cases and the agent runtime orchestration.

## Workspace Status Values

- `preparing`
- `ready`
- `repairing`
- `dirty`
- `missing`
- `unauthorized`
- `error`

## Ensure User Repository Workspace

Ensures the authenticated user's prepared workspace exists for a repository and base branch.

### Request

```http
POST /api/user-workspaces/ensure
Authorization: Bearer <token>
Content-Type: application/json
```

```json
{
  "repository_id": "uuid",
  "sandbox_id": "uuid-or-null",
  "base_branch": "main"
}
```

### Response: Ready or Preparing Complete

```json
{
  "workspace_id": "uuid",
  "repository_id": "uuid",
  "sandbox_id": "uuid",
  "base_branch": "main",
  "workspace_path": "/repos/users/<user>/<repo>/<branch>",
  "status": "ready",
  "reused": true,
  "message": "Workspace reused."
}
```

### Required Behavior

- Must authenticate the user.
- Must verify repository access before returning or creating any workspace.
- Must not return another user's workspace.
- Must serialize concurrent ensure requests for the same user/repository/base branch.
- Must repair missing/unhealthy workspace before reporting `ready`.

## List My Workspaces

Provides optional visibility for diagnostics/admin support. A first implementation may expose this only for internal/debug surfaces.

```http
GET /api/user-workspaces
Authorization: Bearer <token>
```

```json
[
  {
    "workspace_id": "uuid",
    "repository_id": "uuid",
    "base_branch": "main",
    "status": "ready",
    "last_used_at": "2026-07-08T15:00:00Z"
  }
]
```

## Cleanup Workspace

Deletes or marks a stale user workspace for cleanup. This must not affect active conversation workspaces.

```http
DELETE /api/user-workspaces/{workspace_id}
Authorization: Bearer <token>
```

### Required Behavior

- Must only allow the owner or an admin.
- Must not delete active mutating conversation workspaces.
- Must update registry state even if filesystem deletion is already complete.
