<!--
Sync Impact Report
Version change: 1.0.1 -> 1.1.0
Modified principles: VI. UX And API Contracts Must Reduce Friction.
Added sections: Sync Impact Report.
Removed sections: None.
Templates requiring updates:
- .specify/templates/plan-template.md: reviewed, no change required
- .specify/templates/spec-template.md: reviewed, no change required
- .specify/templates/tasks-template.md: reviewed, no change required
- .specify/templates/commands/*.md: not present in this installation
Runtime guidance reviewed:
- AGENTS.md: already aligned with Spec Kit flow
- .agents/skills/frontend-implementation/SKILL.md: updated for governed shadcn/Tailwind migration
- .agents/skills/design-system/SKILL.md: updated for governed shadcn/Tailwind tokens
- .agents/skills/ux-design/SKILL.md: updated for governed shadcn/Tailwind UX decisions
Follow-up TODOs: None.
-->

# CappyCloud Constitution

## Core Principles

### I. Specification Before Non-Trivial Code

Features, architectural changes, API contract changes, frontend flows, agent
runtime behavior, sandbox behavior, persistence changes, and authorization
changes MUST start from Spec Kit artifacts. The expected flow is
`$speckit-specify`, optional `$speckit-clarify`, `$speckit-plan`,
`$speckit-tasks`, optional `$speckit-analyze`, then `$speckit-implement`.

Small bug fixes and urgent operational adjustments MAY use a direct flow when
the requested behavior is already clear. In that case, the implementation still
MUST cite the evidence from code or repository documentation and keep the
change narrowly scoped.

### II. Hexagonal Boundaries Are Mandatory

Backend business logic MUST live in `services/api/app/application/use_cases/`.
HTTP routers under `services/api/app/adapters/primary/http/` MUST parse
requests, call use cases, and return responses only. Routers MUST NOT contain
direct SQL, persistence decisions, domain rules, or provider-specific logic.

External dependencies such as databases, LLM providers, Confluence, sandbox
services, token services, and agent runtimes MUST be accessed through ports in
`services/api/app/ports/` and implemented by adapters. New ports MUST include a
real adapter, an in-memory fake, and contract tests when behavior is shared.

### III. Quality Gates Define Done

Code is not done until the relevant local gates pass or the reason they could
not run is documented. Backend changes MUST respect `ruff check`,
`ruff format --check`, `mypy app/`, and `pytest` with coverage at or above 80%.
Frontend changes under `web/` MUST run the frontend lint/build checks used by
the repository. Critical business logic, authorization, cost, branch
resolution, and runtime context propagation SHOULD include targeted tests that
assert exact behavior and important boundaries.

Public functions and classes MUST have type annotations. Code files MUST stay
within the repository limit of 300 effective lines unless an explicit
repository rule supersedes that limit.

### IV. Runtime Context, Security, And Cost Are Product Behavior

Repository selection, skills, MCP tools, external documentation, models, and
cost data are runtime context. The system MUST NOT assume a fixed repository
catalog, fixed model, fixed skill registry, or fixed documentation source.

Model selection MUST come from conversation, database, or UI configuration when
available. Environment variables are fallback only. Cost reporting MUST use
provider usage and current OpenRouter catalog prices for configured models; a
local token estimate is not the primary source of truth.

Secrets MUST NOT be committed. Cross-user access, closed routes, repository
visibility, and LLM availability MUST be enforced by use cases and tested with
negative cases when changed.

### V. Evidence-Based Answers And External Documentation

Technical answers MUST separate evidence from repository code and evidence from
external documentation. Confluence, Linx Share, observability, and other
external sources MAY be cited only when a configured tool actually returned the
page or record, including real title and URL when available. Missing
documentation MUST be reported as missing instead of inferred.

When information is insufficient, ask for the concrete missing item that
unblocks analysis: error log, service version, selected repository, selected
model, executed flow, or relevant page/result.

### VI. UX And API Contracts Must Reduce Friction

API responses, validation errors, streaming behavior, loading states, and empty
states MUST be explicit enough for the frontend and the user to understand what
happened. User-facing text SHOULD be accessible Portuguese when the product
surface is Portuguese.

Frontend work MUST follow the active frontend design system recorded in the
current Spec Kit plan. Existing features default to the repository's React and
Mantine patterns. A non-trivial design-system migration MAY adopt another
component and theming foundation only when the specification, plan, and tasks
explicitly approve it, update dependent skills/templates, and include migration
and validation tasks for every affected product surface. Parallel UI systems
MUST NOT remain in the same authenticated product surface after migration unless
the Spec Kit artifacts explicitly scope the temporary overlap and its removal.

## Additional Constraints

- Prefer existing repository patterns, ports, adapters, services, and UI
  components before adding abstractions.
- Keep implementation changes close to the requested behavior and avoid
  unrelated refactors.
- Do not revert or overwrite unrelated dirty worktree changes.
- Sandbox and worktree behavior is operationally sensitive; automatic push,
  branch creation, container changes, or network calls MUST be explicit in the
  plan when they are part of a feature.
- Generated artifacts, temporary dumps, local backups, and large files MUST NOT
  be committed unless the specification explicitly calls for them.

## Development Workflow

1. Start with `$speckit-specify` for new non-trivial work.
2. Run `$speckit-clarify` if requirements contain unresolved product,
   authorization, data, UX, or operational questions.
3. Run `$speckit-plan` and ensure its Constitution Check passes before coding.
4. Run `$speckit-tasks` to create dependency-ordered work.
5. Run `$speckit-analyze` when spec, plan, and tasks are broad enough to drift.
6. Run `$speckit-implement` and verify with the gates required by the touched
   areas.

Specs live under `specs/`. Shared Spec Kit scripts and templates live under
`.specify/`. Codex skills for the workflow live under
`.agents/skills/speckit-*/SKILL.md`.

## Governance

This constitution is the highest-priority project rule for Spec Kit artifacts.
If it conflicts with generated specs, plans, or tasks, those artifacts must be
updated. If it conflicts with a newer repository rule, update this constitution
in the same change that updates the source rule.

Amendments require updating this file, checking dependent templates or docs,
and documenting the effect on future Spec Kit plans.

**Version**: 1.1.0
**Ratified**: 2026-06-10
**Last Amended**: 2026-07-10
