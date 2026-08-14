# Patch Audit: OpenClaude 0.28.0 Upgrade

## Baseline

- Production-observed OpenClaude baseline: `0.24.0` at
  `2ff93a10bf88ab6d7030fc4ade5316a7424fa2f9`.
- Local Dockerfile pre-implementation pin:
  `1b7e55058cca57f2f83d7e229441631794286c1a`.
- Target: `0.28.0` at `6e30b40de00868a968bdcaa0c3d0dd915d69d357`.

## Patch Files Present

| Patch | Current Dockerfile use | Initial decision |
|---|---:|---|
| `grep-tool-n-alias.patch` | yes | Rebase/validate against 0.28.0 |
| `multimodal-proto.patch` | yes | Rebase/validate against 0.28.0 |
| `multimodal-grpc-handler.patch` | yes | Rebase/validate against 0.28.0 |
| `read-empty-pages.patch` | yes | Rebase/validate against 0.28.0 |
| `mcp-grpc-integration.patch` | no | Review for obsolete or deferred status |
| `numeric-parameter-grep-guard.patch` | no | Review for obsolete or deferred status |
| `numeric-parameter-grep-wrapper.patch` | no | Review for obsolete or deferred status |
| `worktree-tool-guard.patch` | no | Review for obsolete or deferred status |

## Inline Dockerfile Mutations To Preserve

- Permission mode handling for allow/deny decisions.
- Worktree scope guard before tool execution.
- `request_id` propagation on streamed gRPC responses.
- Attachment/image forwarding to OpenClaude.
- UTF-8-safe string and tool result handling.
- Portuguese permission confirmation acceptance (`sim`, `s`).
- Disabling OpenClaude cross-stream message persistence so CappyCloud remains
  the authorized history source.
- Deferred `detectStubLeaks()` execution.

## Follow-up Evidence

## Compatibility Check: 2026-08-14

Each Dockerfile-applied patch was checked against a clean checkout of
OpenClaude `6e30b40de00868a968bdcaa0c3d0dd915d69d357` with
`git apply --check`.

| Patch | Result | Notes |
|---|---|---|
| `grep-tool-n-alias.patch` | PASS | Applies cleanly |
| `multimodal-proto.patch` | PASS | Applies cleanly |
| `multimodal-grpc-handler.patch` | PASS | Rebased for the upstream `Message` type import and current `server.ts` helpers |
| `read-empty-pages.patch` | PASS | Applies cleanly |

The Dockerfile now applies `multimodal-grpc-handler.patch` without
`--reject || true`, so future patch drift fails the image build immediately
instead of hiding rejected hunks.
