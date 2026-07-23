# UI Contract: Chat Vertical Navigation

## Scope

This contract defines the frontend behavior between the active chat page, marker derivation helper, and the vertical navigation component. It is not an HTTP API contract.

## Inputs

| Input | Provider | Description |
|-------|----------|-------------|
| `messages` | `ActiveChat` | Loaded visible conversation messages in render order. |
| `visibleResultBlocks` | `ActiveChat` / message rendering | Result, file, or output blocks already visible to the user. |
| `explicitDecisions` | Marker helper | Decision-like visible content detected from rendered message/block metadata or text. |
| `scrollViewport` | Active chat scroll viewport ref | Scroll container used for jump and active marker detection. This should use the viewport already present in the chat implementation, including Radix Scroll Area if that is the active component. |
| `targetRefs` | `ActiveChat` message wrappers | Stable refs keyed by marker target id. |
| `isComfortableWidth` | CSS/media query or layout state | Whether the rail should be visible. |
| `streamingState` | Existing chat state | Used to avoid unstable markers for incomplete low-signal fragments. |

## Outputs

| Output | Consumer | Description |
|--------|----------|-------------|
| `markers` | `ChatVerticalNavigation` | Ordered, compacted marker list. |
| `activeMarkerId` | `ChatVerticalNavigation` | Current marker highlighted in the rail. |
| `onMarkerActivate(markerId)` | `ActiveChat` | Scrolls to the marker target and updates active state. |
| `preview` | User | Hover/focus preview for the selected marker. |

## Required Behaviors

1. The rail renders only when the conversation has at least four meaningful markers and the viewport has comfortable desktop width.
2. Each rendered marker is a keyboard-focusable control with an accessible name.
3. Clicking a marker or pressing Enter/Space while focused scrolls the chat viewport to the target location.
4. Manual chat scrolling updates the active marker to the most relevant visible milestone.
5. Hovering or focusing a marker shows a compact preview with actor, title, and excerpt.
6. The preview uses only content already visible in the chat and must not reveal redacted or restricted content.
7. The rail does not overlap message text, the composer, dialogs, drawers, or primary controls.
8. On narrow viewports, no rail affordance is displayed.
9. With very long conversations, lower-priority markers are compacted or grouped while primary milestones remain reachable.
10. If marker derivation fails or returns too few markers, the chat behaves exactly as it does today.

## Acceptance Matrix

| Requirement | Contract Coverage |
|-------------|-------------------|
| FR-001 | Behavior 1 |
| FR-002, FR-002a | Inputs and Behavior 9 |
| FR-003 | Outputs and Behavior 3 |
| FR-004 | Output `activeMarkerId` and Behavior 4 |
| FR-005 | Output `preview` and Behavior 5 |
| FR-006 | Behavior 6 |
| FR-007 | Behavior 2 and Behavior 3 |
| FR-008 | Behavior 7 |
| FR-009 | Behavior 8 |
| FR-010 | Inputs and Behavior 4 |
| FR-011 | Marker validation in data model |
| FR-012 | Behavior 10 |
| FR-013 | Behavior 9 |

## Error And Empty States

- Fewer than the marker threshold: render nothing.
- Missing target ref: skip the marker and keep the chat usable.
- Streaming content without stable visible text: do not create a marker until enough content is available.
- Narrow viewport: hide the rail through responsive layout.
- Reduced motion preference: jump without animated scrolling if implementation uses smooth scroll elsewhere.

## Responsive Baseline

- Initial marker threshold: four meaningful markers.
- Initial desktop breakpoint: `1024px`, unless implementation discovers an existing chat breakpoint that should be reused for consistency.
- Narrow viewport behavior: hide the rail completely instead of showing a drawer, overlay, or collapsed control.
