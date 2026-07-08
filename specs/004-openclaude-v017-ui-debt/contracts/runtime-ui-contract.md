# Runtime/UI Contract: OpenClaude v0.17.1 Upgrade

## Sandbox Build Contract

- `services/sandbox/Dockerfile` must set `OPENCLAUDE_REF` to
  `1b7e55058cca57f2f83d7e229441631794286c1a`.
- The build must fetch from `https://github.com/Gitlawb/openclaude.git` and
  apply only audited local patches.
- The feature does not include production image push, Portainer/Swarm rollout,
  or automatic container replacement.

## gRPC Request Contract

`ChatRequest` continues to carry CappyCloud-owned runtime context:

- `message`
- `working_directory`
- optional `model`
- `session_id`
- `request_id`
- `attachments`
- optional provider base URL/key/format
- optional `permission_mode`

Rules:
- `permission_mode` is resolved by CappyCloud and sent on each request.
- Provider key fields remain internal to gRPC and must never be reflected to the
  browser.
- If OpenClaude v0.17.1 adds internal cache/session behavior, it cannot change
  the visible CappyCloud conversation without CappyCloud persistence.

## Stream Event Contract

Existing UI event families must remain valid:

- text chunk
- tool start
- tool result
- action required
- done with usage
- error
- payload diagnostic

Additional metadata for fallback or session diagnostics may be added only as
sanitized, allowlisted fields. Raw provider responses, prompts, API keys, repo
file contents, and unsanitized tool arguments are forbidden.

## Chat UI Contract

The chat page must show:

- correct active conversation after switch, reload, and session resume;
- correct permission mode for the active conversation;
- startup, resume, retry, action-required, cancellation, failure, and done
  states without duplicated progress;
- useful sanitized tool/provider/runtime errors;
- final model and cost consistent with provider usage and catalog pricing.

## Model Catalog Contract

- Model picker contents come from the CappyCloud authorized catalog.
- Upstream discovery or OpenClaude defaults cannot activate a model by
  themselves.
- If final runtime model differs from the selected model, the final model must
  be authorized before the UI may show success.
- Retired/unavailable models should be shown as unavailable with an authorized
  alternative path.

## Skill Source Contract

- Repository-versioned skills remain active according to selected repository
  context.
- Sandbox/global/database skills remain governed by CappyCloud registration.
- `skill://` sources are visible for audit only until explicitly authorized.
- A runtime-discovered skill source must not override a repository skill with
  the same name.
