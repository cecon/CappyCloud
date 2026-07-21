# Backend Baseline: Conversation And Sandbox Runtime Boundaries

## Files Reviewed

- `services/api/app/adapters/primary/http/conversations.py`
- `services/api/app/application/use_cases/conversations.py`
- `services/api/app/ports/sandbox_runtime.py`
- `services/api/app/adapters/secondary/sandbox_runtime/docker_sidecar.py`

## Current Behavior

- Conversation HTTP routes parse authenticated requests and delegate streaming behavior to use cases.
- `StreamMessage` in `services/api/app/application/use_cases/conversations.py` owns model resolution, permission mode propagation, stream processing, persisted usage and cost calculation.
- Sandbox runtime control is already abstracted through `services/api/app/ports/sandbox_runtime.py`.
- `docker_sidecar.py` calls the sandbox session server runtime endpoints for OpenClaude stop/restart behavior.

## Implementation Constraints

- Slash command authorization and execution decisions must live in application use cases.
- Runtime command discovery/execution must go through a port and real adapter, with fake and contract tests.
- `/model`, `/ctx` and `/cost` must use CappyCloud-authorized model and usage/cost sources.
- HTTP routes for commands must stay thin and avoid SQL/domain decisions.
