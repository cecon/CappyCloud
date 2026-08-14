# Research: OpenClaude Current Upgrade UI Readiness

## Decision: Advance the upgrade target to OpenClaude 0.28.0

**Rationale**: On 2026-08-14 the user explicitly approved advancing the
previously frozen target after release verification showed GitHub release
`v0.28.0` at `6e30b40de00868a968bdcaa0c3d0dd915d69d357`. The npm `latest`
dist-tag still reported `0.27.0`, so CappyCloud pins the GitHub release commit
directly instead of relying on npm metadata.

**Alternatives considered**:

- Track whatever version is latest at implementation time. Rejected because it
  creates unstable UI scope and patch risk.
- Defer target choice to implementation. Rejected because tasks would not be
  testable or traceable.

## Decision: Treat production 0.24.0 as the functional baseline, but re-check before implementation

**Rationale**: Prior production inspection in this thread observed sandbox
package version 0.24.0 at commit `2ff93a10bf88ab6d7030fc4ade5316a7424fa2f9`.
Git tag lookup confirms that commit is `v0.24.0`. The local Dockerfile still
contains an older `OPENCLAUDE_REF`, so planning must explicitly handle local
source/image mismatch before patching.

**Alternatives considered**:

- Use the local Dockerfile pin as the baseline. Rejected because production is
  the product behavior the user questioned.
- Ignore production and plan only from source. Rejected because upgrade risk is
  tied to what users are currently running.

## Decision: Expose live context/token information as a discrete progress indicator

**Rationale**: OpenClaude 0.25.0 highlights live token/context counts, but
CappyCloud cost must remain based on provider usage and catalog pricing. A
discrete execution-time indicator gives users confidence that context is being
processed without confusing progress with final cost.

**Alternatives considered**:

- Hide context/token information entirely. Rejected because it misses a useful
  UX signal from the upgrade.
- Show a detailed always-visible context bar. Rejected because it can crowd the
  chat and imply precision/cost that the product does not own mid-stream.

## Decision: Render subagents as grouped, collapsible activity inside the parent turn

**Rationale**: OpenClaude 0.27.0 introduces subagents from multi-repository
parent sessions. In CappyCloud, the parent conversation remains the visible
source of truth. Grouping subagent activity preserves auditability and context
without turning every auxiliary execution into a separate top-level message.

**Alternatives considered**:

- Hide subagent activity. Rejected because long or complex work would become
  opaque.
- Render each subagent as a separate message. Rejected because it would pollute
  the conversation timeline and make final status harder to read.

## Decision: Keep provider onboarding/OAuth state administrator-only

**Rationale**: OpenClaude 0.25.0 and 0.27.0 add provider onboarding and
auth-ready proxy behavior. CappyCloud already governs providers and model
visibility through authorized catalog/admin surfaces. Exposing provider auth to
regular users could leak operational details or imply permissions they do not
have.

**Alternatives considered**:

- Let users initiate provider auth when a provider is unavailable. Rejected
  because it bypasses catalog governance.
- Hide onboarding completely. Rejected because administrators need actionable
  state when provider auth affects model availability.

## Decision: Validate long-running tool and permission-timeout states through chat activity contracts

**Rationale**: OpenClaude 0.26.0 keeps long-running tools active instead of
tripping guards, and 0.27.0 improves tool-failure guards and permission timeout
reporting. CappyCloud needs user-visible states for active work, stalled work,
timeout, cancellation and final failure, all sanitized for secrets and raw logs.

**Alternatives considered**:

- Treat these as runtime-only changes. Rejected because the user-visible chat
  can still get stuck or show misleading status.
- Add separate diagnostics pages first. Rejected because the chat is the primary
  product surface and needs the core feedback inline.

## Decision: Exclude production deployment and deliver a rollout/rollback runbook

**Rationale**: The user explicitly wants local testing first. Sandbox image
build and local validation are in scope; production rollout is operationally
sensitive and should be a later, deliberate execution using a runbook.

**Alternatives considered**:

- Include production deployment after local tests. Rejected because the user
  scoped production out.
- Provide no deployment guidance. Rejected because upgrade work should still
  leave a safe operational path.

## Decision: Keep upstream branding and terminal-only features out of the CappyCloud UI

**Rationale**: OpenClaude releases include buddy companions, refreshed upstream
web identity and terminal commands. CappyCloud has its own chat-centered visual
direction and authenticated product UI. Terminal-only features should map only
to CappyCloud-native user outcomes when useful.

**Alternatives considered**:

- Mirror OpenClaude terminal/web branding in CappyCloud. Rejected because it
  conflicts with product identity and the active UI theme spec.
- Ignore all terminal-only releases. Rejected because some terminal status
  improvements may have useful chat equivalents.

## Implementation Re-check: OpenClaude target evidence on 2026-08-07

**Result**: Target remains valid and frozen for this feature.

**Evidence captured locally**:

- `git ls-remote --tags https://github.com/Gitlawb/openclaude.git refs/tags/v0.24.0 refs/tags/v0.25.0 refs/tags/v0.26.0 refs/tags/v0.27.0`
  returned:
  - `v0.24.0` -> `2ff93a10bf88ab6d7030fc4ade5316a7424fa2f9`
  - `v0.25.0` -> `0a9bc187a469d492c20fe41d18f75ce693fe2898`
  - `v0.26.0` -> `a3c251f77fbbaece6d95052bada597b9380f9fd2`
  - `v0.27.0` -> `7eeb90fb5bc970776e8f8acef2a2d41ff457865f`
- `npm view @gitlawb/openclaude version dist-tags.latest --json` returned
  `version = 0.27.0` and `dist-tags.latest = 0.27.0`.

**Local baseline re-check**: `services/sandbox/Dockerfile` still referenced
`OPENCLAUDE_REF=1b7e55058cca57f2f83d7e229441631794286c1a` before
implementation. This confirms the planned mismatch: production-observed
baseline is OpenClaude 0.24.0, while the local Dockerfile source pin is older
than the product baseline and must be advanced directly to the frozen 0.27.0
target.

## Implementation Re-check: OpenClaude target evidence on 2026-08-14

**Result**: Target advanced to `0.28.0` by explicit product decision.

**Evidence captured locally**:

- `git ls-remote --tags https://github.com/Gitlawb/openclaude.git "refs/tags/v0.28.0*"`
  returned `v0.28.0` -> `6e30b40de00868a968bdcaa0c3d0dd915d69d357`.
- GitHub release `v0.28.0` is marked latest and was published on 2026-08-11.
- npm metadata for `@gitlawb/openclaude` still reports `0.27.0` as `latest`,
  so the Dockerfile uses the Git commit pin.

**Release themes added to scope**:

- 0.28.0 model-picker catalog rebuild performance.
- 0.28.0 monotonic query watchdog deadlines.
- 0.28.0 Node module compile cache.
