# OpenClaude 0.27.0 Rollout/Rollback Runbook

This runbook documents the later production rollout path for the OpenClaude
0.27.0 sandbox image. It must not be executed as part of local implementation.

## Scope

- Target: OpenClaude `0.27.0` at
  `7eeb90fb5bc970776e8f8acef2a2d41ff457865f`.
- Baseline: production-observed OpenClaude `0.24.0`.
- Execution status for this feature: local validation only.

## Prerequisites

- Local sandbox image build passed.
- API quality gates passed or blockers are documented.
- Frontend quality gates passed or blockers are documented.
- Manual quickstart scenarios 1-5 have recorded evidence.
- Rollback image/tag for the current production sandbox is known.
- Maintenance window and operator owner are defined outside this feature.

## Production Deployment Steps

1. Confirm no newer OpenClaude target was added to this feature scope.
2. Build and publish the reviewed sandbox image through the normal CI/release
   process.
3. Update the production sandbox service image reference in the deployment
   system.
4. Roll one sandbox replica first when the platform supports staged rollout.
5. Validate gRPC startup, model selection, repository worktree setup and chat
   streaming on the staged replica.
6. Continue rollout only after the staged validation passes.

## Post-Deployment Validation

- Sandbox logs show OpenClaude `0.27.0`.
- Existing conversations continue using CappyCloud-visible history.
- Permission mode and worktree guard remain active.
- Chat shows active work, timeout, cancellation and failure states correctly.
- Administrators can see sanitized provider auth/configuration state.
- Regular users cannot see provider onboarding/OAuth state.
- Usage and cost remain based on provider usage and CappyCloud catalog pricing.

## Rollback Triggers

- Sandbox fails to start or gRPC cannot serve requests.
- Permission guard or worktree guard is bypassed.
- Conversation history, repository visibility or model authorization is wrong.
- Raw secrets, tokens, prompts or logs appear in user-facing surfaces.
- Provider/model catalog availability differs from CappyCloud authorization.
- Error rate or latency exceeds the operational threshold for the rollout.

## Rollback Steps

1. Stop the rollout immediately.
2. Restore the previous production sandbox image reference.
3. Restart affected sandbox services.
4. Validate gRPC readiness and a known-good chat scenario.
5. Record the rollback reason and attach local/prod evidence to the incident or
   deployment record.
6. Re-open implementation only after the failed guard, patch or UI contract is
   corrected and revalidated locally.
