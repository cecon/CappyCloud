# Data Model: Chat Vertical Navigation

This feature introduces derived frontend view models only. No database schema, API response, or persisted entity is added.

## ChatNavigationMarker

Represents one important conversation location in the rail.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | yes | Stable UI id for the marker within the active conversation. |
| `targetId` | string | yes | DOM/ref key for the visible chat location to scroll to. |
| `sourceMessageId` | string | no | Message id when the marker comes from a chat message. |
| `sourceBlockId` | string | no | Result, file, activity, or decision block id when available. |
| `kind` | enum | yes | `user_request`, `assistant_final`, `result_block`, `decision`, or `group`. |
| `actor` | enum | yes | `user`, `assistant`, or `system_context` for visible context/result markers. |
| `title` | string | yes | Short label used in preview and accessibility text. |
| `preview` | string | yes | Authorized excerpt derived from visible content. |
| `priority` | number | yes | Higher priority markers survive compaction first. |
| `order` | number | yes | Conversation order used for rail placement. |
| `groupedCount` | number | no | Number of compacted markers represented by a group marker. |

### Validation Rules

- `id` is unique for the active conversation render.
- `targetId` points to exactly one mounted visible chat location.
- `preview` contains only content already visible in the chat.
- `title` and `preview` are trimmed and bounded for compact display.
- Markers keep conversation order even when compacted.
- Low-signal streaming fragments and progress notes do not become markers.

## ActiveConversationLocation

Tracks the marker that best represents the user's current scroll position.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `activeMarkerId` | string | no | Marker id currently selected or most visible. |
| `lastUserJumpAt` | number | no | Timestamp used to avoid scroll observer flicker immediately after a click. |
| `isProgrammaticScroll` | boolean | no | Whether the viewport is currently moving due to marker activation. |

### Validation Rules

- `activeMarkerId` must match an existing marker or be empty.
- Programmatic scroll state clears after the target is reached or after a short timeout.

## MarkerPreview

The compact information shown on hover or keyboard focus.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `markerId` | string | yes | Marker being previewed. |
| `actorLabel` | string | yes | Human-readable actor label. |
| `title` | string | yes | Short marker title. |
| `excerpt` | string | yes | Short visible excerpt. |
| `metadataLabel` | string | no | Optional context such as result/file count or decision type. |

### Validation Rules

- Preview appears for hover and focus.
- Preview does not cover the composer or primary chat content.
- Preview text follows existing product language style.

## MarkerGroup

Represents compacted lower-priority milestones in very long conversations.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | yes | Stable group marker id. |
| `markerIds` | string[] | yes | Original marker ids represented by the group. |
| `rangeLabel` | string | yes | Short label describing the covered conversation range. |
| `primaryMarkerId` | string | yes | Best target when the group is activated. |
| `count` | number | yes | Number of represented markers. |

### Validation Rules

- A group contains at least two markers.
- The primary marker is one of the grouped markers.
- Primary user requests, final responses, explicit decisions, and result/file markers are preserved before lower-priority milestones are grouped.

## State Transitions

```text
normal -> hovered -> normal
normal -> focused -> normal
normal -> active
active -> normal
normal -> compact
compact -> grouped
grouped -> active
```

State changes are local UI state. They do not alter conversation data.
