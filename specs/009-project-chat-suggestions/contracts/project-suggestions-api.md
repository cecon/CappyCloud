# Contract: Project Suggestions API

All endpoints are authenticated under `/api`.

## GET `/api/project-suggestions`

Return user-visible suggestions for the selected project empty state.

**Query Parameters**

- `repo_slug` (required): Selected workspace/repository slug.
- `limit` (optional): Integer from 3 to 4. Defaults to 4.

**Authorization**

- Current user must have access to the repository identified by `repo_slug`.
- Response must not include suppressed suggestions or suggestions from another repository.

**Success 200**

```json
{
  "repo_slug": "cappycloud",
  "repo_name": "CappyCloud",
  "state": "calibrated",
  "last_calibrated_at": "2026-07-22T03:00:00Z",
  "cards": [
    {
      "id": "7d8b4c1c-5e45-4f88-9e26-63f5a9a8a111",
      "title": "Entender o fluxo de sandbox",
      "prompt": "Explique como o sandbox e o worktree sao preparados para uma nova conversa neste projeto.",
      "category": "explore",
      "source": "initial_context",
      "freshness_state": "fresh"
    }
  ],
  "diagnostic": {
    "using_initial_context": true,
    "reason": null
  }
}
```

**States**

- `calibrated`: Active suggestions include question-history improvements.
- `initial`: Suggestions come from project metadata/documents/skills only.
- `fallback`: Metadata-only fallback was used because documents/skills/history were unavailable.
- `empty`: No safe suggestion can be shown.
- `error`: Suggestions could not be loaded; UI should keep composer usable.

**Errors**

- `401`: Not authenticated.
- `403`: User has no access to the repository.
- `404`: Repository not found or inactive.
- `422`: Invalid `repo_slug` or `limit`.

## POST `/api/project-suggestions/{repository_id}/recalibrate`

Queue or run recalibration for one project.

**Authorization**

- Admin role only.

**Request**

```json
{
  "trigger": "manual",
  "force": false
}
```

**Success 202**

```json
{
  "repository_id": "9b5300ad-8116-40cd-996b-1a1a0fc7b999",
  "run_id": "c3a7e33f-90a0-4afd-b34d-2f387b37a123",
  "status": "queued"
}
```

**Errors**

- `403`: User is not allowed to recalibrate suggestions.
- `404`: Repository not found.
- `409`: A recent queued/running recalibration already exists and `force` is false.

## PATCH `/api/project-suggestions/{suggestion_id}`

Suppress or reactivate one suggestion.

**Authorization**

- Admin role only.

**Request**

```json
{
  "status": "suppressed",
  "reason": "Texto duplicado"
}
```

**Success 200**

```json
{
  "id": "7d8b4c1c-5e45-4f88-9e26-63f5a9a8a111",
  "status": "suppressed",
  "suppressed_at": "2026-07-22T14:10:00Z"
}
```

**Errors**

- `403`: User is not allowed to manage suggestions.
- `404`: Suggestion not found.
- `422`: Unsupported status transition.

## GET `/api/project-suggestions/{repository_id}/status`

Return operational state for administrators.

**Authorization**

- Admin role only.

**Success 200**

```json
{
  "repository_id": "9b5300ad-8116-40cd-996b-1a1a0fc7b999",
  "active_count": 4,
  "candidate_count": 2,
  "suppressed_count": 1,
  "last_run": {
    "id": "c3a7e33f-90a0-4afd-b34d-2f387b37a123",
    "trigger": "daily",
    "status": "succeeded",
    "finished_at": "2026-07-22T03:00:00Z",
    "eligible_message_count": 48,
    "eligible_user_count": 7
  }
}
```

## Frontend Contract

- The empty chat state calls `GET /api/project-suggestions?repo_slug=<slug>` after a repository is selected.
- Loading state keeps existing cards area stable and does not disable the composer.
- On success, card click sets the composer text to `card.prompt` only.
- On `403`/`404`, no suggestions from that repository are rendered.
- On network/error states, the UI may show metadata-only local placeholders only if they are not project-specific claims.
