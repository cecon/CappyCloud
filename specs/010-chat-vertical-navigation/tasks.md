# Tasks: Chat Vertical Navigation

**Input**: Design documents from `/specs/010-chat-vertical-navigation/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/vertical-navigation-ui.md, quickstart.md

**Tests**: Frontend validation uses the existing `web/package.json` scripts: `pnpm --dir web lint` and `pnpm --dir web build`. The repository does not currently expose a frontend test script, so no new test framework is introduced by these tasks.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel because it touches a different file or does not depend on incomplete work.
- **[Story]**: Which user story the task belongs to.
- Every task includes an exact file path.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm the current chat render and prepare the frontend files without changing behavior.

- [x] T001 Inspect the existing `ActiveChat` scroll viewport, `messages.map`, and message wrapper points in `web/src/pages/ChatPage.tsx`
- [x] T002 Inspect existing chat layout classes and responsive conventions in `web/src/components/chat.module.css`
- [x] T003 [P] Create the empty rail component file `web/src/components/chat/ChatVerticalNavigation.tsx`
- [x] T004 [P] Create the empty rail style module `web/src/components/chat/ChatVerticalNavigation.module.css`
- [x] T005 [P] Create the marker helper module `web/src/components/chat/chatNavigationMarkers.ts`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Define the shared view model and component contract used by every user story.

**CRITICAL**: No user story work can begin until this phase is complete.

- [x] T006 Define `ChatNavigationMarker`, `MarkerPreview`, marker kind, actor, priority, and grouping types in `web/src/components/chat/chatNavigationMarkers.ts`
- [x] T007 Implement bounded text helpers for marker titles and previews in `web/src/components/chat/chatNavigationMarkers.ts`
- [x] T008 Define `ChatVerticalNavigation` props, empty-state return, and marker button skeleton in `web/src/components/chat/ChatVerticalNavigation.tsx`
- [x] T009 Add base rail CSS variables, fixed dimensions, focus style placeholders, and hidden empty state styles in `web/src/components/chat/ChatVerticalNavigation.module.css`

**Checkpoint**: Foundation ready - user story implementation can now begin.

---

## Phase 3: User Story 1 - Navigate Long Chat History (Priority: P1) MVP

**Goal**: Show meaningful milestones for long conversations and let the user jump to a selected chat location.

**Independent Test**: Open a conversation with at least eight meaningful milestones, click markers, and confirm the intended turn becomes visible and identifiable.

### Implementation for User Story 1

- [x] T010 [P] [US1] Implement `deriveChatNavigationMarkers` for user requests, final assistant responses, visible result/file blocks, and explicit decisions in `web/src/components/chat/chatNavigationMarkers.ts`
- [x] T011 [US1] Add stable milestone target refs for rendered messages in `web/src/pages/ChatPage.tsx`
- [x] T012 [US1] Render `ChatVerticalNavigation` beside the chat message viewport when derived markers meet the threshold in `web/src/pages/ChatPage.tsx`
- [x] T013 [US1] Implement marker activation with `scrollIntoView` or equivalent viewport scrolling in `web/src/pages/ChatPage.tsx`
- [x] T014 [US1] Implement active marker synchronization from manual scroll position in `web/src/pages/ChatPage.tsx`
- [x] T015 [US1] Enforce the initial two-marker render threshold in `web/src/components/chat/chatNavigationMarkers.ts`
- [x] T016 [US1] Style normal, active, and selected marker states in `web/src/components/chat/ChatVerticalNavigation.module.css`
- [x] T017 [US1] Validate the P1 manual scenarios from `specs/010-chat-vertical-navigation/quickstart.md`

**Checkpoint**: User Story 1 is fully functional and testable independently.

---

## Phase 4: User Story 2 - Understand Each Navigation Marker (Priority: P2)

**Goal**: Let users preview each marker before jumping, including keyboard users.

**Independent Test**: Hover and keyboard-focus markers, then verify each preview shows actor, title or excerpt, and enough context to distinguish nearby turns.

### Implementation for User Story 2

- [x] T018 [P] [US2] Extend marker derivation with actor labels, preview excerpts, result/file labels, and decision labels in `web/src/components/chat/chatNavigationMarkers.ts`
- [x] T019 [US2] Filter deleted, failed, redacted, restricted, and non-visible details before building marker previews in `web/src/components/chat/chatNavigationMarkers.ts`
- [x] T020 [US2] Render hover and focus preview content in `web/src/components/chat/ChatVerticalNavigation.tsx`
- [x] T021 [US2] Add accessible names, `aria-current`, and keyboard activation behavior for marker buttons in `web/src/components/chat/ChatVerticalNavigation.tsx`
- [x] T022 [US2] Style marker previews so they avoid message content and composer overlap in `web/src/components/chat/ChatVerticalNavigation.module.css`
- [x] T023 [US2] Validate the P2 hover, focus, and keyboard scenarios from `specs/010-chat-vertical-navigation/quickstart.md`

**Checkpoint**: User Stories 1 and 2 both work independently.

---

## Phase 5: User Story 3 - Keep The Chat Focused And Responsive (Priority: P3)

**Goal**: Keep the rail useful on desktop, hidden on narrow screens, and scannable for very long conversations.

**Independent Test**: Review desktop and narrow viewports, confirm the rail never overlaps primary controls, and verify compact/group behavior with 60+ milestones.

### Implementation for User Story 3

- [x] T024 [P] [US3] Implement marker priority compaction and group marker creation in `web/src/components/chat/chatNavigationMarkers.ts`
- [x] T025 [US3] Render compact and grouped marker states in `web/src/components/chat/ChatVerticalNavigation.tsx`
- [x] T026 [US3] Add desktop positioning, `1024px` narrow viewport hiding, density limits, and reduced-motion handling in `web/src/components/chat/ChatVerticalNavigation.module.css`
- [x] T027 [US3] Adjust chat layout spacing only if needed to prevent rail overlap in `web/src/components/chat.module.css`
- [x] T028 [US3] Validate the P3 desktop, narrow viewport, 60+ milestone, and streaming scenarios from `specs/010-chat-vertical-navigation/quickstart.md`

**Checkpoint**: All user stories are independently functional.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final quality, safety, and repository gates.

- [x] T029 Review all new frontend code files for the 300 effective line limit in `web/src/components/chat/ChatVerticalNavigation.tsx`
- [x] T030 [P] Review marker helper code for the 300 effective line limit in `web/src/components/chat/chatNavigationMarkers.ts`
- [x] T031 [P] Review rail CSS for text fit, focus visibility, and no overlapping UI in `web/src/components/chat/ChatVerticalNavigation.module.css`
- [x] T032 Run `pnpm --dir web lint` from repository root for `web/package.json`
- [x] T033 Run `pnpm --dir web build` from repository root for `web/package.json`
- [x] T034 Record any gate that could not run and the reason in `specs/010-chat-vertical-navigation/quickstart.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on Setup completion and blocks all user stories.
- **User Story 1 (Phase 3)**: Depends on Foundational completion and is the MVP.
- **User Story 2 (Phase 4)**: Depends on Foundational completion; integrates naturally after US1 because previews attach to rendered markers.
- **User Story 3 (Phase 5)**: Depends on Foundational completion; can start after US1 marker rendering exists.
- **Polish (Phase 6)**: Depends on all desired user stories being complete.

### User Story Dependencies

- **US1 - Navigate Long Chat History**: No dependency on other stories after Foundation.
- **US2 - Understand Each Navigation Marker**: Can be developed after Foundation, but final UI validation requires marker rendering from US1.
- **US3 - Keep The Chat Focused And Responsive**: Can develop helper/CSS pieces after Foundation, but full validation requires US1 rendering and US2 preview behavior.

### Within Each User Story

- Helper changes before component behavior that consumes them.
- Component behavior before CSS polish that depends on rendered states.
- Integration in `ChatPage.tsx` before manual validation.

---

## Parallel Opportunities

- T003, T004, and T005 can run in parallel after T001/T002 context is understood.
- T010 can run in parallel with T011 because helper derivation and page refs touch different files.
- T018 can run in parallel with T020 only after the base marker/component props from Foundation exist.
- T024 and T026 can run in parallel because compaction logic and responsive styling touch different files.
- T030 and T031 can run in parallel during polish.

## Parallel Example: User Story 1

```bash
Task: "T010 [P] [US1] Implement deriveChatNavigationMarkers for user requests and final assistant responses in web/src/components/chat/chatNavigationMarkers.ts"
Task: "T011 [US1] Add stable milestone target refs for rendered messages in web/src/pages/ChatPage.tsx"
```

## Parallel Example: User Story 2

```bash
Task: "T018 [P] [US2] Extend marker derivation with actor labels, preview excerpts, result/file labels, and decision labels in web/src/components/chat/chatNavigationMarkers.ts"
Task: "T020 [US2] Render hover and focus preview content in web/src/components/chat/ChatVerticalNavigation.tsx"
```

## Parallel Example: User Story 3

```bash
Task: "T024 [P] [US3] Implement marker priority compaction and group marker creation in web/src/components/chat/chatNavigationMarkers.ts"
Task: "T026 [US3] Add desktop positioning, 1024px narrow viewport hiding, density limits, and reduced-motion handling in web/src/components/chat/ChatVerticalNavigation.module.css"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup.
2. Complete Phase 2: Foundational.
3. Complete Phase 3: User Story 1.
4. Stop and validate P1 with the quickstart long-conversation scenario.
5. Run `pnpm --dir web lint` and `pnpm --dir web build` if delivering the MVP alone.

### Incremental Delivery

1. Add US1 to make long-chat jumping usable.
2. Add US2 to make marker choice understandable and accessible.
3. Add US3 to refine responsive behavior, density, and visual safety.
4. Run the full quickstart scenarios and frontend gates.

### Parallel Team Strategy

1. One developer owns `web/src/pages/ChatPage.tsx` integration.
2. One developer owns `web/src/components/chat/chatNavigationMarkers.ts`.
3. One developer owns `web/src/components/chat/ChatVerticalNavigation.tsx` and `web/src/components/chat/ChatVerticalNavigation.module.css`.
4. Merge through US1 first, then layer US2 and US3.

## Notes

- Keep the feature frontend-only unless implementation uncovers an existing chat data gap.
- Do not persist marker state or add API endpoints in this feature.
- Preserve hidden behavior for short conversations and narrow viewports.
- Do not expose redacted, failed, deleted, or restricted details in previews.
