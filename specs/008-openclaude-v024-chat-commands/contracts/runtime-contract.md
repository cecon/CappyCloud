# Runtime Contract: OpenClaude v0.24

## Runtime Pin

- Target version: `v0.24.0`
- Target commit: `2ff93a10bf88ab6d7030fc4ade5316a7424fa2f9`
- Source: `https://github.com/Gitlawb/openclaude`

`services/sandbox/Dockerfile` must pin `OPENCLAUDE_REF` to the target commit, not to a floating branch.

## Patch Audit

Every local OpenClaude patch or inline edit must be classified before completion:

| Item | Required decision |
|---|---|
| `grep-tool-n-alias.patch` | retained, changed, removed, or obsolete |
| `multimodal-proto.patch` | retained, changed, removed, or obsolete |
| `multimodal-grpc-handler.patch` | retained, changed, removed, or obsolete |
| `read-empty-pages.patch` | retained, changed, removed, or obsolete |
| inline worktree guard edit | retained, changed, removed, or obsolete |
| inline request id propagation edit | retained, changed, removed, or obsolete |
| inline permission mode edit | retained, changed, removed, or obsolete |
| inline multimodal submit edit | retained, changed, removed, or obsolete |
| inline session persistence suppression | retained, changed, removed, or obsolete |
| inline UTF-8/gRPC string edit | retained, changed, removed, or obsolete |
| inline command confirmation localization edit | retained, changed, removed, or obsolete |

## Required Preserved Behavior

- Per-request model override remains controlled by CappyCloud.
- Per-request provider base URL/API key/API format remain internal and are never logged or rendered to users.
- Per-request `permission_mode` remains sanitized and applies to each request.
- CappyCloud remains source of visible conversation history; OpenClaude session/cache behavior must not replace it.
- Worktree guard remains active for tool execution.
- Multimodal attachment behavior remains compatible with the CappyCloud stream.
- Usage/cost events continue to report enough information for CappyCloud to persist provider usage and final model.

## Command Discovery

Runtime command discovery may come from OpenClaude metadata, static runtime introspection, or a CappyCloud adapter. Regardless of source:

- All upstream commands discovered by the runtime must be represented in the CappyCloud command catalog.
- Terminal-only commands must be marked unavailable unless a safe headless path exists.
- Runtime operations such as `/update` cannot update production or pushed images through this feature.

## Validation

- `git ls-remote --tags https://github.com/Gitlawb/openclaude.git refs/tags/v0.24.0` must match the target commit.
- Sandbox image build must complete with the target commit.
- Runtime smoke must confirm at least one normal response, one tool event, one action-required flow, one cancellation, and one command catalog discovery flow.
