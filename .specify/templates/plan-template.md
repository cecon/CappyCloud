# Implementation Plan: [FEATURE]

**Branch**: `[###-feature-name]` | **Date**: [DATE] | **Spec**: [link]

**Input**: Feature specification from `/specs/[###-feature-name]/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

[Extract from feature spec: primary requirement + technical approach from research]

## Technical Context

<!--
  ACTION REQUIRED: Replace the content in this section with the technical details
  for the project. The structure here is presented in advisory capacity to guide
  the iteration process.
-->

**Language/Version**: [Python/FastAPI, TypeScript/React, Node sandbox, or NEEDS CLARIFICATION]

**Primary Dependencies**: [FastAPI, SQLAlchemy, React, Mantine, Docker sandbox, OpenRouter, or NEEDS CLARIFICATION]

**Storage**: [PostgreSQL, Redis, files/worktrees, or N/A]

**Testing**: [ruff, mypy, pytest, frontend lint/build, or NEEDS CLARIFICATION]

**Target Platform**: [Docker Compose stack, sandbox container, browser UI, or NEEDS CLARIFICATION]

**Project Type**: [API, frontend, agent runtime, sandbox, docs, or NEEDS CLARIFICATION]

**Performance Goals**: [domain-specific, e.g., 1000 req/s, 10k lines/sec, 60 fps or NEEDS CLARIFICATION]

**Constraints**: [domain-specific, e.g., <200ms p95, <100MB memory, offline-capable or NEEDS CLARIFICATION]

**Scale/Scope**: [domain-specific, e.g., 10k users, 1M LOC, 50 screens or NEEDS CLARIFICATION]

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [ ] Non-trivial change has a spec, plan, and task breakdown, or the direct
      bugfix/operational exception is justified.
- [ ] Backend business rules are in `services/api/app/application/use_cases/`;
      HTTP routers stay thin and contain no SQL or domain decisions.
- [ ] External systems are behind ports/adapters, with fakes and contract tests
      when behavior is shared.
- [ ] Security, authorization, repository visibility, and cross-user access
      implications are explicit.
- [ ] Runtime context is dynamic: selected repos, skills, MCPs, docs, model, and
      cost are not hardcoded.
- [ ] Required gates are planned: `ruff check`, `ruff format --check`,
      `mypy app/`, `pytest`, and frontend lint/build when `web/` changes.
- [ ] Evidence requirements are clear for code, external docs, URLs, and line
      references when available.
- [ ] Sandbox/worktree/Git behavior is explicit, especially branch creation,
      automatic push, container rebuilds, and network calls.

## Project Structure

### Documentation (this feature)

```text
specs/[###-feature]/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)
<!--
  ACTION REQUIRED: Replace the placeholder tree below with the concrete layout
  for this feature. Delete unused options and expand the chosen structure with
  real paths (e.g., apps/admin, packages/something). The delivered plan must
  not include Option labels.
-->

```text
services/api/
├── app/
│   ├── application/use_cases/   # business logic
│   ├── domain/                  # entities and value objects
│   ├── ports/                   # ABC ports
│   ├── adapters/primary/http/   # FastAPI routers and DI
│   └── adapters/secondary/      # DB, provider, sandbox adapters
└── tests/
    ├── unit/
    ├── adapter/
    └── integration/

services/cappycloud_agent/       # agent pipeline and runtime context
services/sandbox/                # Docker sandbox and session sidecar
web/                             # React + Mantine frontend
docs/                            # technical documentation
```

**Structure Decision**: [Document the selected structure and reference the real
directories captured above]

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| [e.g., 4th project] | [current need] | [why 3 projects insufficient] |
| [e.g., Repository pattern] | [specific problem] | [why direct DB access insufficient] |
