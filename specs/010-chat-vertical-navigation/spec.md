# Feature Specification: Chat Vertical Navigation

**Feature Branch**: `codex/chat-vertical-navigation-spec`

**Created**: 2026-07-22

**Status**: Draft

**Input**: User description: "quero implementar no meu chat essa navegacao vertical que vejo no codex"

## Clarifications

### Session 2026-07-22

- Q: Quais itens devem virar marcadores na navegacao vertical? -> A: Marcadores so para marcos importantes: pedidos do usuario, respostas finais, blocos de resultado/arquivos e decisoes relevantes.
- Q: Como a navegacao vertical deve se comportar em telas estreitas? -> A: Visivel em desktop/larguras confortaveis; oculta em telas estreitas.
- Q: Como a rail deve lidar com conversas muito longas? -> A: Limitar a rail a marcos principais e agrupar ou compactar excesso em conversas muito longas.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Navigate Long Chat History (Priority: P1)

As a user working through a long chat, I want a compact vertical navigation rail that shows important milestones in the conversation so I can jump back to earlier requests, decisions, final responses, and results without manually scrolling through the whole page.

**Why this priority**: Long agent conversations can contain many updates, outputs, and corrections. Fast navigation improves continuity and makes the chat usable after substantial work.

**Independent Test**: Can be fully tested by opening a conversation with at least eight meaningful milestones, using the vertical navigation to jump between them, and confirming the selected milestone becomes visible and identifiable.

**Acceptance Scenarios**:

1. **Given** a conversation with multiple user and assistant turns, **When** the user clicks a marker in the vertical navigation, **Then** the chat scrolls to the corresponding turn and highlights the selected position.
2. **Given** the user scrolls the conversation manually, **When** a different turn becomes the primary visible section, **Then** the vertical navigation updates its active marker.

---

### User Story 2 - Understand Each Navigation Marker (Priority: P2)

As a user scanning the navigation rail, I want each marker to expose a short preview of the related turn so I can choose the right place before jumping.

**Why this priority**: A rail with only anonymous ticks is fast but easy to misread. Short previews make navigation more confident without adding clutter.

**Independent Test**: Can be tested by hovering or focusing markers and verifying that each preview summarizes the related turn with the actor, a short title or excerpt, and enough context to distinguish it from nearby turns.

**Acceptance Scenarios**:

1. **Given** the user hovers a marker, **When** the marker has a related chat turn, **Then** a compact preview appears near the rail without covering the main message content.
2. **Given** the user navigates by keyboard focus, **When** a marker receives focus, **Then** the same preview information is available and the marker can be activated without a mouse.

---

### User Story 3 - Keep The Chat Focused And Responsive (Priority: P3)

As a user on desktop or other comfortable-width screens, I want the vertical navigation to help without stealing space from the conversation or becoming distracting.

**Why this priority**: The chat remains the primary workspace. Navigation should be helpful on dense desktop sessions and graceful on smaller screens.

**Independent Test**: Can be tested across desktop and narrow viewports by confirming the rail appears only when space is comfortable, does not overlap messages, input controls, modals, or side panels, and is hidden on narrow screens.

**Acceptance Scenarios**:

1. **Given** the viewport has enough horizontal space, **When** the chat is open, **Then** the rail appears alongside the conversation content without shifting text unexpectedly.
2. **Given** the viewport is narrow, **When** the chat is open, **Then** the navigation is hidden so the conversation and composer remain fully usable.

### Edge Cases

- A new or short conversation with too few turns should not show a noisy navigation rail.
- Streaming or still-loading assistant turns should appear only when they have enough visible content to be useful.
- Deleted, failed, redacted, or restricted content must not expose hidden details in marker previews.
- Markers should remain stable when older history loads, new messages arrive, or the user switches conversations.
- Very long conversations should keep the rail scannable by representing important milestones and grouping or compacting excess markers when needed.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide a compact vertical navigation rail for conversations that contain enough meaningful turns to benefit from quick navigation.
- **FR-002**: The navigation rail MUST represent meaningful chat milestones, including user requests, final assistant responses, notable result or file blocks, and explicit decisions when they are visible in the conversation.
- **FR-002a**: The navigation rail MUST NOT create a marker for every individual chat message when those messages are intermediate updates, streaming fragments, or low-signal progress notes.
- **FR-003**: Each marker MUST map to exactly one visible conversation location and activation MUST move the user to that location.
- **FR-004**: The currently visible or selected conversation location MUST be reflected in the navigation rail with a distinct active state.
- **FR-005**: Users MUST be able to reveal a short preview for a marker before activating it.
- **FR-006**: Marker previews MUST include only information the current user is already authorized to see in the conversation.
- **FR-007**: The rail MUST be usable with keyboard navigation and screen-reader-friendly names for markers and actions.
- **FR-008**: The rail MUST avoid overlapping the composer, message content, dialogs, drawers, and other primary controls.
- **FR-009**: The rail MUST be hidden on narrow viewports where it would compete with the conversation or composer.
- **FR-010**: The system MUST keep marker positions and active state accurate when messages stream in, the user scrolls, or the selected conversation changes.
- **FR-011**: The system MUST not create duplicate or stale markers when the same conversation is reloaded.
- **FR-012**: The feature MUST preserve the existing chat behavior when the navigation rail is not shown or cannot be computed.
- **FR-013**: The rail MUST limit visual density in very long conversations by keeping primary milestones visible and grouping or compacting lower-priority excess markers.

### Key Entities *(include if feature involves data)*

- **Navigation Marker**: A derived item representing one important conversation milestone. Key attributes include actor, preview text, marker type, ordering, visibility state, and target location.
- **Active Conversation Location**: The currently selected or most visible turn used to synchronize scroll position with the navigation rail.
- **Marker Preview**: A short, authorized summary or excerpt shown before navigation.

### Runtime Context, Security & Evidence *(mandatory when applicable)*

- **RC-001**: The feature uses the currently selected conversation and repository context already visible in the chat; it must not assume a fixed project, model, or skill registry.
- **RC-002**: Conversation visibility and repository access rules remain unchanged. The rail must only expose markers for content that the current user can already view in the chat.
- **RC-003**: No external documentation evidence is required for the product behavior. Visual inspiration comes from the attached Codex-style screenshot, but the CappyCloud behavior is defined by this specification.
- **RC-004**: No sandbox, worktree, Git, container, or network behavior is part of this feature.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In a conversation with at least 20 meaningful turns, users can jump from the newest turn to a chosen earlier turn in under 5 seconds.
- **SC-002**: At least 90% of navigation marker activations land with the intended turn visible without additional manual scrolling.
- **SC-003**: On supported desktop viewports, the rail does not cover chat text, composer controls, or action buttons in visual review.
- **SC-004**: On narrow viewports, users can send a message and read the latest response with the navigation rail hidden and no navigation element obstructing the workflow.
- **SC-005**: Keyboard users can focus, preview, and activate markers for a representative long conversation without losing focus context.
- **SC-006**: In a conversation with at least 60 meaningful milestones, the rail remains visually scannable and provides a way to reach primary milestones without rendering every milestone as a full-size marker.

## Assumptions

- The first version derives markers from important user requests, final assistant responses, visible result/file blocks, and explicit decision points already present in the loaded conversation.
- The rail appears only when a conversation has enough markers to justify the extra UI, with a reasonable default threshold of at least four meaningful markers.
- The preview text can use existing message excerpts or existing display labels; no new stored summaries are required for the first version.
- Mobile and very narrow layouts hide the rail instead of trying to match the desktop visual exactly.
- The visual treatment should feel consistent with the current CappyCloud chat surface while borrowing the compact timeline concept shown in the reference image.
- When marker volume exceeds the available rail space, user requests, final results, and explicit decisions have higher display priority than progress updates or intermediate assistant messages.
