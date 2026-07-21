# Runtime Audit: OpenClaude v0.24 Chat Commands

## Baseline Evidence

- Verified target tag on 2026-07-21: `refs/tags/v0.24.0` resolves to `2ff93a10bf88ab6d7030fc4ade5316a7424fa2f9`.
- Current sandbox pin before implementation: `services/sandbox/Dockerfile` sets `OPENCLAUDE_REF=1b7e55058cca57f2f83d7e229441631794286c1a`.
- Current Dockerfile applies patch files from `services/sandbox/patches/` and multiple inline `perl -0pi` edits against `/openclaude/src/grpc/server.ts`.
- Runtime startup path: `services/sandbox/env_init.sh` starts the session server on `SESSION_SERVER_PORT` and OpenClaude gRPC on `GRPC_PORT`, default `50051`.
- Current sidecar status path: `services/sandbox/runtime_handler.js` exposes `/runtime/status`, `/runtime/stop-openclaude` and `/runtime/restart-openclaude`.

## Patch Inventory

| Item | Current source | Decision | Notes |
|---|---|---|---|
| `grep-tool-n-alias.patch` | `services/sandbox/patches/grep-tool-n-alias.patch` | retained | `git apply --check` passes against `2ff93a10bf88ab6d7030fc4ade5316a7424fa2f9`. |
| `multimodal-proto.patch` | `services/sandbox/patches/multimodal-proto.patch` | retained | `git apply --check` passes against `2ff93a10bf88ab6d7030fc4ade5316a7424fa2f9`. |
| `multimodal-grpc-handler.patch` | `services/sandbox/patches/multimodal-grpc-handler.patch` | shimmed for v0.24 | The legacy patch still produces rejects against v0.24.0, but `services/sandbox/patch_openclaude_grpc_v024.js` and `services/sandbox/cappycloud_grpc_helpers_v024.ts` now restore the required imports/helpers explicitly before build. Runtime inspection confirms `cappycloudGrpcString`, `cappycloudValidateToolScope`, `cappycloudPayloadDiagnostic` and MCP command loading are present after `env_init`. |
| `read-empty-pages.patch` | `services/sandbox/patches/read-empty-pages.patch` | retained | `git apply --check` passes against `2ff93a10bf88ab6d7030fc4ade5316a7424fa2f9`. |
| `worktree-tool-guard.patch` | `services/sandbox/patches/worktree-tool-guard.patch` | rebase required | Fails against v0.24.0 at `src/grpc/server.ts:24`. |
| `mcp-grpc-integration.patch` | `services/sandbox/patches/mcp-grpc-integration.patch` | rebase required | Fails against v0.24.0 at `src/grpc/server.ts:7`. |
| numeric grep patches | `services/sandbox/patches/numeric-parameter-grep-*.patch` | rebase required | `numeric-parameter-grep-wrapper.patch` fails at `src/grpc/server.ts:180`; `numeric-parameter-grep-guard.patch` fails at `src/grpc/server.ts:51`. |
| inline gRPC edits | `services/sandbox/Dockerfile`, `services/sandbox/env_init.sh`, `services/sandbox/patch_openclaude_grpc_v024.js` | retained with v0.24 shim | Docker build completes against v0.24.0. Runtime logs show startup provider, context-window and Azure auth needles are now missing, while OpenAI usage shim and gRPC dynamic model patches still apply. The v0.24 shim restores CappyCloud helper definitions that the legacy gRPC patch no longer applies cleanly. |

## Runtime Health Status

- `services/sandbox/runtime_handler.js` now verifies `127.0.0.1:${GRPC_PORT:-50051}` before returning `openclaude: "running"`.
- `/runtime/status` returns `stopped` when the stop sentinel exists, `running` when the gRPC port accepts TCP, and `unhealthy` when the sidecar is alive but OpenClaude is not accepting gRPC.
- `services/sandbox/session_server.js` uses the same runtime health aggregation for `/health`, preventing the misleading production state where the sandbox container and HTTP sidecar are alive but OpenClaude gRPC is down.

## Validation Log

- Sandbox build against v0.24.0: pass on 2026-07-21 with `docker build --build-arg OPENCLAUDE_REF=2ff93a10bf88ab6d7030fc4ade5316a7424fa2f9 -f services/sandbox/Dockerfile -t cappycloud-sandbox:openclaude-v024-check .`.
- Build warning: `multimodal-grpc-handler.patch` still reports 7 rejects, but the required CappyCloud helper surface is restored by the v0.24 patcher before build and verified in the final image.
- Sandbox runtime smoke: pass on 2026-07-21 for container startup, `/runtime/status`, `/health`, OpenClaude gRPC startup log and post-entrypoint helper inspection. Observed `/runtime/status`: `{"openclaude":"running","grpc_port":50051}`; observed `/health`: `{"status":"ok","openclaude":"running","sessions":0}`; logs included `gRPC Server running at 0.0.0.0:50051`. Post-entrypoint inspection found `cappycloudGrpcString`, `cappycloudValidateToolScope`, `cappycloudPayloadDiagnostic` and `getMcpToolsCommandsAndResources`.
- The image does not include `nc`; TCP status should use `/runtime/status` or an installed probe instead of assuming `nc -z` is available inside the container.
- Production push/deploy: explicitly out of scope for this feature.
