# Implementation Plan: Chat Vertical Navigation

**Branch**: `codex/chat-vertical-navigation-spec` | **Date**: 2026-07-22 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/010-chat-vertical-navigation/spec.md`

**Note**: This plan was produced by the `/speckit-plan` workflow for a frontend-only chat navigation feature.

## Summary

Implement a compact desktop-only vertical navigation rail for long chat conversations. The rail will be derived client-side from the currently visible conversation messages and result blocks, showing only meaningful milestones such as user requests, final assistant responses, visible results/files, and explicit decisions. The technical approach is to add a dedicated chat component plus pure marker-derivation helpers under `web/src/components/chat/`, then wire the component into `ActiveChat` with stable target refs and scroll synchronization.

## Technical Context

**Language/Version**: TypeScript with React 19 in `web/`; CSS Modules for scoped styling.

**Primary Dependencies**: Existing React chat surface and the current scroll viewport implementation in `web/`, backed by the dependencies already declared in `web/package.json` such as Radix Scroll Area when used by the active chat; no new runtime package is planned.

**Storage**: N/A. Markers are derived from loaded conversation state and are not persisted.

**Testing**: Frontend checks for touched UI: `pnpm --dir web lint` and `pnpm --dir web build`. Add targeted frontend tests only if the existing web test setup supports the touched helper/component without introducing a new test framework.

**Target Platform**: Browser UI in the existing CappyCloud web app and Docker deployment.

**Project Type**: Frontend.

**Performance Goals**: Smooth scroll and active-marker updates for conversations with at least 60 meaningful milestones; avoid expensive full-message recomputation during scroll.

**Constraints**: Preserve existing chat behavior when hidden or unavailable; show the rail only when at least two meaningful markers exist; hide the rail below the desktop breakpoint selected during implementation, initially planned at `1024px`; expose only content already visible to the current user; keep new code files within the 300 effective line repository limit.

**Scale/Scope**: One authenticated chat screen, with long conversations containing 20+ meaningful turns and very long conversations containing 60+ milestones.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] Non-trivial change has a spec, plan, and task breakdown, or the direct bugfix/operational exception is justified.
- [x] Backend business rules are in `services/api/app/application/use_cases/`; HTTP routers stay thin and contain no SQL or domain decisions. This feature does not touch backend code.
- [x] External systems are behind ports/adapters, with fakes and contract tests when behavior is shared. This feature does not add external systems.
- [x] Security, authorization, repository visibility, and cross-user access implications are explicit. Previews are derived only from already visible chat content.
- [x] Runtime context is dynamic: selected repos, skills, MCPs, docs, model, and cost are not hardcoded. The rail reads only the active conversation state.
- [x] Required gates are planned: `ruff check`, `ruff format --check`, `mypy app/`, `pytest`, and frontend lint/build when `web/` changes. Only frontend lint/build are required unless backend files are touched later.
- [x] Evidence requirements are clear for code, external docs, URLs, and line references when available. No external documentation evidence is required for this UI behavior.
- [x] Sandbox/worktree/Git behavior is explicit, especially branch creation, automatic push, container rebuilds, and network calls. No sandbox, Git, container, or network behavior is part of the feature.

## Project Structure

### Documentation (this feature)

```text
specs/010-chat-vertical-navigation/
|-- plan.md
|-- research.md
|-- data-model.md
|-- quickstart.md
|-- contracts/
|   `-- vertical-navigation-ui.md
|-- checklists/
|   `-- requirements.md
`-- spec.md
```

### Source Code (repository root)

```text
web/
`-- src/
    |-- pages/
    |   `-- ChatPage.tsx
    `-- components/
        |-- chat/
        |   |-- ChatVerticalNavigation.tsx
        |   |-- ChatVerticalNavigation.module.css
        |   `-- chatNavigationMarkers.ts
        `-- chat.module.css
```

**Structure Decision**: Implement the visible rail as `web/src/components/chat/ChatVerticalNavigation.tsx`, keep marker derivation and compaction in `web/src/components/chat/chatNavigationMarkers.ts`, and make `ChatPage.tsx` responsible only for passing messages, target refs, active state, and scroll callbacks. Use a small new CSS module for the rail styling; only adjust `chat.module.css` if the chat layout needs a stable attachment area.

## Phase 0: Research

See [research.md](./research.md). All open product questions from clarification are resolved.

## Phase 1: Design

See [data-model.md](./data-model.md), [contracts/vertical-navigation-ui.md](./contracts/vertical-navigation-ui.md), and [quickstart.md](./quickstart.md).

## Complexity Tracking

No constitution violations or complexity exceptions are required.
