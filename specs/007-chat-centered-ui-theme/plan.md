# Implementation Plan: Chat-Centered UI Theme

**Branch**: `007-chat-centered-ui-theme` | **Date**: 2026-07-08 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/007-chat-centered-ui-theme/spec.md`

## Summary

Migrate every authenticated CappyCloud web screen to the `tmp/Cappy` chat-centered UX: chat becomes the primary layout surface, current duplicated chat side menus are replaced by the reference support rails, secondary/admin navigation moves into the user menu, and admin areas open as console/modal/panel overlays over the chat experience.

The implementation approach is a frontend redesign of `web/` using React 19, Vite, shadcn/ui, Tailwind CSS v4, CSS theme tokens, lucide icons, and the existing backend/API contracts. No backend, agent, sandbox, Git, or persistence behavior is planned unless a screen cannot be rendered from current contracts.

## Technical Context

**Language/Version**: TypeScript with React 19.2.4; Vite 8.0.4; existing backend remains Python/FastAPI but is not in scope for behavior changes.

**Primary Dependencies**: Current frontend uses Mantine 9.0.2, React Router 7.14.1, Tabler icons, CSS Modules, and Vite. Planned frontend foundation adds shadcn/ui, Tailwind CSS v4 via `@tailwindcss/vite`, Radix-backed shadcn components, `class-variance-authority`, `clsx`, `tailwind-merge`, `tw-animate-css`, and `lucide-react`.

**Storage**: N/A for new persistence. Existing local storage keys may be migrated or retired only for UI preferences such as theme and nav state.

**Testing**: `cd web && pnpm install`, `pnpm run lint`, `pnpm run build`; browser smoke checks for authenticated routes and reference states. Backend gates are not required unless implementation changes backend contracts.

**Target Platform**: Authenticated browser UI served by the existing Vite frontend and Docker Compose development stack.

**Project Type**: Frontend redesign and design-system migration.

**Performance Goals**: Initial authenticated shell usable within 2 seconds on a normal development machine after assets load; route transitions and overlay open/close interactions visually respond within 150 ms; chat scrolling remains smooth with long messages and tool/activity cards.

**Constraints**: No horizontal page scrolling for core desktop/notebook viewports; maintain accessible Portuguese UI text; preserve authorization behavior for admin/super-admin/user views; keep backend and runtime context dynamic; avoid committing generated dumps or temporary files from `tmp/`.

**Scale/Scope**: All existing authenticated routes in `web/src/App.tsx`: `/`, `/chat`, `/runs`, `/analytics`, `/skills`, `/mcp`, `/settings`, `/change-password`, `/admin/users`, `/admin/sandboxes`, `/admin/repositories`, `/admin/skills-global`, `/admin/models`, `/admin/providers`, plus redirects that must remain sane. Login remains public but should not visually clash with the new theme.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] Non-trivial change has a spec, plan, and task breakdown, or the direct bugfix/operational exception is justified.
- [x] Backend business rules are in `services/api/app/application/use_cases/`; HTTP routers stay thin and contain no SQL or domain decisions.
- [x] External systems are behind ports/adapters, with fakes and contract tests when behavior is shared.
- [x] Security, authorization, repository visibility, and cross-user access implications are explicit.
- [x] Runtime context is dynamic: selected repos, skills, MCPs, docs, model, and cost are not hardcoded.
- [x] Required gates are planned: frontend lint/build are required when `web/` changes; backend gates are required only if backend files are touched.
- [x] Evidence requirements are clear for code, external docs, URLs, and line references when available.
- [x] Sandbox/worktree/Git behavior is explicit: none is planned for this feature.

**Governance note**: Constitution v1.1.0 authorizes Spec Kit-approved design-system migrations. This feature uses that path for the authenticated frontend migration to shadcn/ui and Tailwind, with dependent local skills and validation tasks included before implementation.

## Project Structure

### Documentation (this feature)

```text
specs/007-chat-centered-ui-theme/
|-- plan.md
|-- research.md
|-- data-model.md
|-- quickstart.md
|-- contracts/
|   `-- ui-contract.md
|-- checklists/
|   `-- requirements.md
`-- spec.md
```

### Source Code (repository root)

```text
web/
|-- package.json                # add Tailwind/shadcn dependencies and scripts if needed
|-- package-lock.json           # or migrate intentionally if package manager changes
|-- vite.config.ts              # add @tailwindcss/vite and @ alias
|-- tsconfig.json               # add @/* alias
|-- tsconfig.app.json           # add @/* alias
`-- src/
    |-- main.tsx                # remove MantineProvider when migration is complete
    |-- index.css               # Tailwind import, CSS variables, theme tokens
    |-- App.tsx                 # preserve route guards; route admin entries into overlay pattern
    |-- api.ts                  # reuse current API contracts
    |-- components/
    |   |-- ui/                 # shadcn/ui generated primitives
    |   |-- layout/             # chat-centered app shell, user menu, rails, overlays
    |   |-- chat/               # message, composer, activity, permission/result cards
    |   `-- admin/              # console panels for admin workflows
    |-- pages/                  # migrate all authenticated pages to new shell/components
    `-- lib/
        |-- utils.ts            # shadcn cn helper
        `-- theme.ts            # optional typed theme helpers if needed
```

**Structure Decision**: Keep the existing single `web/` app and route guards. Introduce shadcn/ui primitives under `web/src/components/ui/`, feature composition under domain folders, and shared theme tokens in `web/src/index.css`. Do not create a separate frontend app.

## Complexity Tracking

| Complexity | Why Needed | Simpler Alternative Rejected Because |
|------------|------------|-------------------------------------|
| Replace Mantine foundation with shadcn/ui + Tailwind | The clarified feature explicitly requires shadcn/ui and Tailwind as the component/theming foundation for all authenticated screens, and constitution v1.1.0 allows this when governed by Spec Kit artifacts. | Keeping Mantine would not satisfy the user's clarified requirement for this redesign. |
| Migrate all authenticated screens in one release | The clarified scope requires no authenticated screen to remain in the previous visual language. | Incremental migration would reduce risk but would leave mixed UX, violating the spec and demo goal. |

## Phase 0: Research

See [research.md](research.md).

Key decisions:

- Use Tailwind CSS v4 through the first-party Vite plugin.
- Use shadcn/ui in existing-project mode with `@/*` aliases and generated primitives committed under `web/src/components/ui/`.
- Replace, rather than wrap, Mantine for authenticated surfaces.
- Preserve existing API calls and authorization guards.

## Phase 1: Design

See [data-model.md](data-model.md), [contracts/ui-contract.md](contracts/ui-contract.md), and [quickstart.md](quickstart.md).

Design outputs:

- Theme tokens model for dark/light modes and semantic component states.
- UI contract for route coverage, authorization, navigation, overlays, chat states, and visual acceptance.
- Validation quickstart for setup, build checks, and manual smoke scenarios.

## Post-Design Constitution Check

- [x] Spec and plan exist; tasks must be generated before implementation.
- [x] Backend boundaries remain unaffected unless future tasks discover a missing contract.
- [x] Authorization must remain enforced through `RequireAdmin`, `RequireSuperAdmin`, route guards, and backend checks.
- [x] Runtime context remains conversation/API driven; UI cannot hardcode repositories, models, costs, docs, or skills.
- [x] Frontend gates are explicit: `pnpm run lint` and `pnpm run build`.
- [x] External documentation evidence used: official shadcn/ui Vite installation docs and official Tailwind CSS Vite installation docs.
- [x] Sandbox/worktree/Git/container changes are out of scope.

**Constitution risk status**: Resolved by constitution v1.1.0 and setup tasks T001-T004, which align governance and local frontend/design/UX skills before implementation.
