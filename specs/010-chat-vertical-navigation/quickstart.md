# Quickstart: Chat Vertical Navigation

## Prerequisites

- Use the repository's existing Node and package-manager setup for `web/`.
- If `pnpm` is unavailable locally, enable it with Corepack according to the repository setup.
- No backend service, database migration, or external API configuration is required for this feature.

## Implementation Checklist

1. Add marker derivation and compaction helpers under `web/src/components/chat/`.
2. Add `ChatVerticalNavigation` and its CSS module under `web/src/components/chat/`.
3. Wire the rail into `ActiveChat` in `web/src/pages/ChatPage.tsx` using stable target refs for milestone locations.
4. Keep the rail hidden for conversations with fewer than four meaningful markers and for viewports below the selected desktop breakpoint.
5. Ensure marker buttons support hover, focus, Enter, and Space.
6. Verify preview text is derived only from content already visible in the chat, excluding deleted, failed, redacted, or restricted details.

## Local Verification

Run the frontend gates after implementation:

```bash
pnpm --dir web lint
pnpm --dir web build
```

If the Docker web service is used for review, rebuild and start it with the repository's configured compose workflow, then open the existing local CappyCloud web URL.

## Manual Test Scenarios

1. Open a short conversation with fewer than four meaningful milestones. The rail should not render.
2. Open or seed a long conversation with at least 20 meaningful milestones. On desktop width, the rail should be visible.
3. Click a marker near the top while currently viewing the newest response. The intended turn should become visible in under 5 seconds.
4. Scroll manually through the chat. The active marker should update as different milestones become primary in view.
5. Hover a marker. A compact preview should appear without covering message content or the composer.
6. Tab to a marker. The same preview should appear, and Enter or Space should navigate to the target.
7. Resize to a narrow viewport. The rail should be hidden, and the composer should remain fully usable.
8. Use a very long conversation with at least 60 milestones. The rail should compact or group lower-priority markers while preserving primary milestones.
9. While an assistant response streams, verify the rail does not create unstable markers for low-signal fragments.
10. If the conversation includes failed, redacted, or restricted content, verify previews do not expose hidden details.
