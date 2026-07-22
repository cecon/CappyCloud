# Implementation Plan: Project-Aware Chat Suggestions

**Branch**: `[]` | **Date**: 2026-07-22 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/009-project-chat-suggestions/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

Replace the static initial chat quick-action cards with project-aware suggestions that appear as soon as a repository/workspace is selected. The implementation will add persisted suggestion and calibration state in PostgreSQL, application-layer use cases for visibility, generation, suppression and recalibration, thin FastAPI endpoints, a daily APScheduler job plus document/skill change invalidation, and a frontend integration in the existing chat empty state.

The MVP will generate initial suggestions from already-known CappyCloud context only: repository metadata plus documents and skills already registered or ingested for that repository. Question history will improve suggestions later through aggregate anonymized project-level signals. No sandbox code scan, worktree access, external documentation crawl, or LLM-dependent generation is required for the empty-state display.

## Technical Context

**Language/Version**: Python 3.12/FastAPI backend, SQLAlchemy async persistence, TypeScript/React 19 frontend, Vite web app.

**Primary Dependencies**: FastAPI, SQLAlchemy, Alembic, APScheduler, React, existing shadcn/Tailwind and legacy chat CSS patterns, existing repository/document/skill/conversation/message tables.

**Storage**: PostgreSQL for project suggestions, calibration runs, and durable metadata. Redis/worktrees/sandbox files are not used by this feature.

**Testing**: Backend: `ruff check`, `ruff format --check`, `mypy app/`, `pytest`. Frontend: `pnpm lint`, `pnpm build` from `web/`.

**Target Platform**: CappyCloud Docker Compose/API stack and browser chat UI. No sandbox container rebuild, Git operation, branch creation, push, or production deployment is part of this plan.

**Project Type**: API + frontend + scheduled backend job + database migration.

**Performance Goals**: Fetch visible suggestions in under 2 seconds for 95% of project selection smoke checks; keep the user-facing endpoint read-only and independent of sandbox readiness.

**Constraints**: Business logic stays in `services/api/app/application/use_cases/`; HTTP routers stay thin; repository visibility and cross-user history privacy are enforced before returning or recalibrating suggestions; generated suggestions must be concise Portuguese text and never expose raw prompts, authors, secrets, or private conversation snippets.

**Scale/Scope**: 3 to 4 cards per selected project; daily recalibration plus debounced recalibration after document/skill changes; MVP covers the empty initial chat state only, not in-conversation suggestions.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] Non-trivial change has a spec, plan, and task breakdown, or the direct
      bugfix/operational exception is justified.
- [x] Backend business rules are in `services/api/app/application/use_cases/`;
      HTTP routers stay thin and contain no SQL or domain decisions.
- [x] External systems are behind ports/adapters, with fakes and contract tests
      when behavior is shared.
- [x] Security, authorization, repository visibility, and cross-user access
      implications are explicit.
- [x] Runtime context is dynamic: selected repos, skills, MCPs, docs, model, and
      cost are not hardcoded.
- [x] Required gates are planned: `ruff check`, `ruff format --check`,
      `mypy app/`, `pytest`, and frontend lint/build when `web/` changes.
- [x] Evidence requirements are clear for code, external docs, URLs, and line
      references when available.
- [x] Sandbox/worktree/Git behavior is explicit, especially branch creation,
      automatic push, container rebuilds, and network calls.

## Project Structure

### Documentation (this feature)

```text
specs/009-project-chat-suggestions/
|-- plan.md
|-- research.md
|-- data-model.md
|-- quickstart.md
|-- contracts/
|   |-- project-suggestions-api.md
|-- checklists/
|   |-- requirements.md
`-- tasks.md
```

### Source Code (repository root)

```text
services/api/
|-- alembic/versions/
|   `-- <timestamp>_add_project_chat_suggestions.py
|-- app/
|   |-- domain/
|   |   `-- project_suggestions.py
|   |-- ports/
|   |   `-- project_suggestions.py
|   |-- application/use_cases/
|   |   |-- project_suggestions.py
|   |   `-- project_suggestion_recalibration.py
|   |-- adapters/primary/http/
|   |   |-- project_suggestions.py
|   |   `-- deps.py
|   |-- adapters/secondary/persistence/
|   |   `-- sqlalchemy_project_suggestions.py
|   `-- infrastructure/
|       |-- orm_models_project_suggestions.py
|       `-- project_suggestion_scheduler.py
`-- tests/
    |-- unit/use_cases/
    |   |-- test_project_suggestions.py
    |   `-- test_project_suggestion_recalibration.py
    |-- adapter/
    |   `-- test_project_suggestion_repo.py
    `-- integration/
        `-- test_api_project_suggestions.py

web/
|-- src/api.ts
|-- src/pages/ChatPage.tsx
`-- src/components/chat.module.css
```

**Structure Decision**: Use the existing API hexagonal layout and the existing chat empty-state surface. Add a dedicated suggestion domain/port/use-case slice instead of putting SQL or suggestion rules in `workspaces.py`, `conversations.py`, or `ChatPage.tsx`. Reuse APScheduler already initialized in `services/api/app/main.py` for daily recalibration.

## Complexity Tracking

No constitution violations are planned.

## Phase 0 Research Summary

See [research.md](research.md).

Key decisions:

- Generate initial cards from repository metadata plus already registered/ingested documents and skills.
- Store suggestions and calibration runs in first-class PostgreSQL tables.
- Use aggregate anonymized question-history signals only; never store or render raw prompt snippets as suggestions.
- Use daily APScheduler recalibration plus debounced document/skill change scheduling.
- Keep the MVP independent from sandbox readiness and LLM generation.

## Phase 1 Design Summary

See [data-model.md](data-model.md), [contracts/project-suggestions-api.md](contracts/project-suggestions-api.md), and [quickstart.md](quickstart.md).

Post-design Constitution Check remains passing:

- Business rules are isolated in planned use cases.
- New persistence is accessed through a project-suggestion port with SQLAlchemy and in-memory implementations plus adapter contract tests.
- User-facing reads and admin operations enforce repository access and role gates.
- Cross-user history is anonymized and aggregated before it can affect cards.
- No sandbox/worktree/Git/container behavior is introduced.
