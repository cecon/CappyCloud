# Research: Chat Vertical Navigation

## Decision 1: Derive markers on the client from visible chat state

**Decision**: Build navigation markers from the messages, assistant outputs, visible result/file blocks, and explicit decision text already loaded in the active chat.

**Rationale**: The first version needs no persistence, API contract, or background recalibration. It also keeps authorization behavior simple: if the chat does not render the content for the current user, the rail cannot preview it.

**Alternatives considered**:

- Persisted navigation summaries: rejected for the first version because it adds storage, invalidation, authorization checks, and migration work before proving the UI behavior.
- Server-generated markers: rejected because the chat already has the display data needed for a frontend-only milestone rail.

## Decision 2: Add a dedicated rail component and pure helper module

**Decision**: Implement `ChatVerticalNavigation` as a new chat component and keep marker derivation/compaction in a pure helper module.

**Rationale**: `ChatPage.tsx` is already large. New behavior should be isolated so the page only coordinates scroll refs and event handlers.

**Alternatives considered**:

- Inline the rail directly in `ChatPage.tsx`: rejected because it increases an already-large file and makes later testing harder.
- Reuse `MessageTimeline.tsx`: rejected for now because this feature is a spatial navigation control tied to the chat scroll viewport, not a standalone message timeline.

## Decision 3: Use stable DOM targets and scroll synchronization

**Decision**: Each marker maps to one visible chat location. Activation scrolls that target into the chat viewport. Active state is computed from the currently visible milestone target, using either `IntersectionObserver` scoped to the scroll viewport or throttled viewport measurements during implementation.

**Rationale**: This keeps behavior aligned with what the user sees and avoids adding route changes or URL anchors.

**Alternatives considered**:

- Index-based scroll offsets: rejected because streaming messages and expanding result cards can change heights.
- URL hash navigation: rejected because this is an in-page chat aid and should not mutate app navigation state.

## Decision 4: Desktop-only rail with responsive hiding

**Decision**: Show the rail only at comfortable desktop widths and hide it on narrow screens.

**Rationale**: The chat and composer are primary. On narrow screens, a persistent rail would compete with reading and sending messages.

**Alternatives considered**:

- Mobile drawer or overlay: rejected for the first version because the clarified requirement is to hide on narrow screens.

## Decision 5: Compact very long conversations by priority

**Decision**: Keep primary milestones visible and compact or group lower-priority markers when density exceeds available rail space.

**Rationale**: The rail must stay scannable with 60+ milestones. User requests, final assistant responses, results/files, and explicit decisions matter more than intermediate progress.

**Alternatives considered**:

- Render every marker at full size: rejected because it becomes unreadable and hard to target in long conversations.
- Fixed maximum marker count only: rejected because it can hide important milestones if the selection is not priority-aware.

## Decision 6: Accessible marker controls

**Decision**: Markers are keyboard-focusable controls with accessible names. Hover and focus expose the same preview, and Enter/Space activation navigates to the target.

**Rationale**: The feature is navigation, so it must support keyboard and screen-reader users without requiring a mouse.

**Alternatives considered**:

- Decorative ticks with mouse-only hover: rejected because it fails keyboard navigation and reduces discoverability.

## Decision 7: Validate with frontend gates and focused visual scenarios

**Decision**: Validate implementation with `pnpm --dir web lint`, `pnpm --dir web build`, and manual or browser-driven visual checks for desktop, narrow viewport, streaming, and long-history scenarios.

**Rationale**: This is a frontend-only UX feature. Backend gates are not relevant unless implementation later touches backend files.

**Alternatives considered**:

- Full backend test suite: rejected as unnecessary for this isolated UI change.
