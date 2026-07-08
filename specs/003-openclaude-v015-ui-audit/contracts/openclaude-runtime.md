# Contract: OpenClaude Runtime Permission Mode

This contract covers internal API to agent pipeline to gRPC propagation.

## Pipeline body

The API use case passes the resolved mode to `AgentPort.pipe` through the
existing `body` dict:

```json
{
  "conversation_id": "uuid",
  "user_id": "uuid",
  "repos": [],
  "session_root": "/repos/sessions/...",
  "override_model": "anthropic/claude-sonnet-4",
  "permission_mode": "request_permissions"
}
```

Rules:

- The value is sanitized and already validated by the API/use case.
- Missing or unknown values inside the agent pipeline fall back to
  `request_permissions`.
- The pipeline must not infer warning severity from provider configuration.

## gRPC ChatRequest

`proto/openclaude.proto` adds a new optional string field:

```proto
message ChatRequest {
  string message = 1;
  string working_directory = 2;
  reserved 3;
  optional string model = 4;
  string session_id = 5;
  string request_id = 6;
  repeated Attachment attachments = 7;
  optional string provider_base_url = 8;
  optional string provider_api_key = 9;
  optional string provider_api_format = 10;
  optional string permission_mode = 11;
}
```

Compatibility:

- Existing clients that omit `permission_mode` continue to behave as
  `request_permissions`.
- The field must never include user-provided free text.

## Runtime mapping

| Permission mode | Runtime behavior |
|---|---|
| `request_permissions` | Use normal OpenClaude permission prompts and `ActionRequired` events. |
| `accept_edits` | Auto-approve edit tools inside CappyCloud hard boundaries; other actions keep normal prompts. |
| `plan` | Keep execution planning/read-only; mutating tools are denied or require switching mode. |
| `auto` | Auto-approve OpenClaude permission prompts inside CappyCloud hard boundaries. |
| `bypass_permissions` | Bypass OpenClaude permission prompts inside CappyCloud hard boundaries. |

## Legacy parameter cleanup

The request-scoped `permission_mode` is the only active source of OpenClaude
permission behavior after this upgrade.

Cleanup rules:

- Process-wide auto-approval defaults such as `OPENCLAUDE_AUTO_APPROVE=1` must
  not remain active in sandbox startup.
- Patch files and patch-generation helpers must not regenerate env-only
  auto-approval behavior.
- Existing external clients that omit `permission_mode` fall back to
  `request_permissions`, not to an old permissive sandbox default.
- If a legacy environment variable remains temporarily for compatibility, it
  must be ignored for permission behavior and documented as obsolete.

CappyCloud hard boundaries always remain active:

- repository authorization;
- worktree path guard;
- sandbox isolation;
- explicit external-action gates for push, PR, deployment, network, or container
  changes when those gates apply;
- secret redaction and no raw provider keys in logs/UI.

## Local patch audit

The implementation must classify each local OpenClaude patch after rebasing to
v0.15.0:

- retained unchanged;
- changed for v0.15.0;
- removed because upstreamed;
- removed because obsolete.

Patch audit results are recorded in `quickstart.md` or implementation notes
before the feature is considered complete.
