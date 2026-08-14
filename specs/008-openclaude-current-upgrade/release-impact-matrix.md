# Release Impact Matrix: OpenClaude 0.25.0-0.28.0

Target: OpenClaude `0.28.0` at
`6e30b40de00868a968bdcaa0c3d0dd915d69d357`.

Baseline: production-observed OpenClaude `0.24.0` at
`2ff93a10bf88ab6d7030fc4ade5316a7424fa2f9`.

## Decisions

| Release theme | Affected surface | UI decision | Rationale |
|---|---|---|---|
| 0.25.0 live context/token visibility | Chat | Adapt UI | Show a discrete execution-time context indicator. Do not present it as cost. |
| 0.25.0 provider onboarding and catalog changes | Admin providers/model picker | Adapt UI | Provider auth/setup state is administrator-only; regular users see catalog-governed availability only. |
| 0.25.0 terminal/web upstream polish | Authenticated UI | Out of scope | CappyCloud brand and authenticated product navigation remain authoritative. |
| 0.26.0 long-running tool behavior | Chat activity | Validate existing and adapt states | Keep active work visible without premature stale failure; terminal states remain explicit. |
| 0.26.0 runtime/tool hardening | Agent/API stream | Runtime-only with UI validation | Normalize failures into sanitized Portuguese events; do not expose raw logs or secrets. |
| 0.27.0 auth-ready loopback proxy hosts | Admin providers | Adapt UI | Expose sanitized next actions only to administrators. |
| 0.27.0 new Ling/Macaron catalog entries | Model picker/catalog | Validate existing | New upstream models must pass CappyCloud authorization, capability, context and pricing rules. |
| 0.27.0 refreshed OpenClaude web identity | Authenticated UI | Out of scope | Do not mirror upstream branding in CappyCloud. |
| 0.27.0 subagents from multi-repository parent sessions | Chat activity | Adapt UI | Group auxiliary work inside the parent turn as collapsible activity. |
| 0.27.0 tool-failure guard, permission timeout, stats and status UI | Chat diagnostics | Adapt UI | Show actionable states for timeout, cancellation, failed work and context processing. |
| 0.28.0 model-picker catalog rebuild performance | Model picker/catalog | Validate existing | CappyCloud catalog remains authoritative; no model change is implied by execution profile controls. |
| 0.28.0 monotonic query watchdog deadlines | Agent/API stream | Runtime-only with UI validation | Long-running streams should remain observable through runtime states and heavy-iteration notices. |
| 0.28.0 Node module compile cache | Sandbox build/runtime | Runtime-only | Improves local startup characteristics; no CappyCloud UI surface required. |
| OpenClaude buddy companions and terminal-only commands | Navigation/menu | Out of scope | Do not add menu entries unless a later CappyCloud-native product outcome is specified. |

## Validation Mapping

- Chat/context/subagent behavior: quickstart scenarios 1-3.
- Admin provider/model visibility: quickstart scenario 4.
- Branding and terminal-only exclusions: quickstart scenario 5.
- Sandbox patch/runtime compatibility: local image build and patch audit.
