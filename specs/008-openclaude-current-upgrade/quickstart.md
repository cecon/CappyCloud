# Quickstart: OpenClaude 0.27.0 Local Validation

This guide validates the feature locally after implementation. Production
deployment is out of scope for this feature.

## Prerequisites

- Docker Desktop or compatible local Docker environment is running.
- The CappyCloud local stack can be started from the repository root.
- Local environment variables are configured for the normal development stack.
- OpenClaude target is frozen at `0.27.0`.
- The local implementation has completed the tasks generated from this plan.

## Static Evidence Checks

1. Confirm the active Spec Kit feature points to this plan.

   ```powershell
   Get-Content .specify/feature.json
   Select-String -Path AGENTS.md -Pattern "008-openclaude-current-upgrade"
   ```

   Expected: both references point to `specs/008-openclaude-current-upgrade`.

2. Confirm OpenClaude target evidence.

   ```powershell
   git ls-remote --tags https://github.com/Gitlawb/openclaude.git |
     Select-String "refs/tags/v0.27.0"
   npm view @gitlawb/openclaude version dist-tags.latest --json
   ```

   Expected: tag `v0.27.0` is present and npm latest is `0.27.0`.

## Build And Local Stack Validation

1. Build the sandbox image with the updated target.

   ```powershell
   docker build -f services/sandbox/Dockerfile -t cappycloud-sandbox-openclaude-v0270-check .
   ```

   Expected: build completes and local patches either apply cleanly or have
   documented replacements.

2. Start the local stack using the repository's normal local workflow.

   ```powershell
   docker compose up -d --build
   ```

   Expected: API, web, postgres, redis and sandbox containers become healthy or
   ready according to local stack behavior.

## Automated Gates

Run the relevant repository gates after implementation:

```powershell
cd services/api
ruff check .
ruff format --check .
mypy app/
pytest
cd ..\..\web
pnpm install
pnpm lint
pnpm build
```

Expected: all gates pass, or any local environment blocker is documented with
the exact command and error.

## Manual UI Scenarios

### Scenario 1: Discrete Context Indicator

1. Open the authenticated local web UI.
2. Start a conversation that causes a non-trivial context payload.
3. Watch the turn while it is executing.

Expected:

- A discrete context/progress indicator appears during execution.
- It does not display cost.
- Final usage/cost appears only after provider usage is known.

### Scenario 2: Long-Running Tool Activity

1. Send a prompt that triggers a long-running tool.
2. Keep the conversation open until the tool completes or fails.

Expected:

- The UI continues to show active work.
- No premature stale/failure state appears while work is still progressing.
- Failure, cancellation or success is clear within 10 seconds of terminal state.

### Scenario 3: Grouped Subagent Activity

1. Use a multi-repository context or prompt that triggers auxiliary/subagent
   work once supported by the runtime.
2. Inspect the parent turn.

Expected:

- Subagent activity is grouped and collapsible inside the parent turn.
- It is not rendered as unrelated top-level chat messages.
- Expanded details remain sanitized.

### Scenario 4: Provider Auth State Is Admin-Only

1. As a regular user, open model selection with a provider/model unavailable.
2. As an administrator, open the provider/model admin surface.

Expected:

- Regular users do not see onboarding/OAuth setup.
- Administrators can see applicable provider auth/configuration states.
- No secrets are displayed.

### Scenario 5: Terminal-Only/Branding Features Stay Out

1. Review the authenticated UI after the upgrade.
2. Search for upstream buddy, mascot, startup-logo or terminal-command UI.

Expected:

- CappyCloud branding remains intact.
- Terminal-only OpenClaude features do not appear unless mapped to a
  CappyCloud-native state in this feature.

## Rollout/Rollback Runbook Validation

Before closing this feature, verify that a runbook exists and includes:

- Production prerequisites.
- Deployment steps.
- Post-deployment validation checks.
- Rollback trigger points.
- Rollback steps.
- Local validation evidence required before execution.

Expected: the runbook can be reviewed without executing production changes.
