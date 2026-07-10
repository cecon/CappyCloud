# UI Contract: Chat-Centered Theme Migration

## Scope

This contract defines expected UI behavior for the authenticated web app after the redesign. It is not a backend API contract.

## Route Contract

| Route | Access | Presentation Contract |
|-------|--------|-----------------------|
| `/` | authenticated | Opens the chat-centered shell or routes into the primary chat/start experience. |
| `/chat` | authenticated | Shows the primary chat surface, conversation support rail, context bar, message stream, and composer. |
| `/runs` | authenticated | Opens from user menu as a redesigned console/panel or routed overlay. |
| `/agentic-delivery` | authenticated | Opens from user menu as a redesigned console/panel or routed overlay. |
| `/analytics` | authenticated | Opens from user menu as a redesigned console/panel or routed overlay. |
| `/skills` | authenticated | Opens from user menu as a redesigned console/panel or routed overlay. |
| `/mcp` | authenticated | Opens from user menu/admin console as redesigned MCP management. |
| `/settings` | super-admin currently | Preserves current access rules and uses redesigned settings/account surface. |
| `/change-password` | authenticated | Uses redesigned account surface and remains reachable from the user menu. |
| `/admin/users` | admin | Opens redesigned admin console/panel for user management. |
| `/admin/sandboxes` | admin | Opens redesigned admin console/panel for sandbox management. |
| `/admin/repositories` | admin | Opens redesigned admin console/panel for repository management. |
| `/admin/skills-global` | super-admin | Opens redesigned admin console/panel for global skills. |
| `/admin/models` | admin/super-admin according to current rules | Opens redesigned admin console/panel for model catalog. |
| `/admin/providers` | admin/super-admin according to current rules | Opens redesigned admin console/panel for providers. |

## Navigation Contract

- The primary authenticated shell centers chat.
- The old global sidebar navigation is removed from the chat path.
- The current duplicated two-sidebar chat layout is removed.
- Conversation/history support remains discoverable according to `tmp/Cappy`.
- Secondary navigation and administration are available through the user menu.
- Direct URLs for protected/admin routes still work and preserve authorization checks.

## Authorization Contract

- `ProtectedPage` behavior remains: anonymous/error users are redirected to `/login`.
- `must_change_password` users are redirected to `/change-password`.
- Admin-only and super-admin-only screens keep route-level guards.
- Menu visibility mirrors permissions but does not replace guards.
- UI must not expose repository, sandbox, model, provider, or user-management actions that the current user cannot execute.

## Theme Contract

- Theme foundation is shadcn/ui + Tailwind.
- Dark and light modes are supported when theme switching is available.
- Theme variables cover background, foreground, card/panel, popover, border, input, ring/focus, primary, secondary, muted, accent, destructive, success, warning, and chart/status colors if needed.
- Shared components use semantic classes/tokens; hardcoded one-off colors require justification.

## Component State Contract

Every shared interactive component must provide:

- default
- hover
- active/pressed
- focus-visible
- disabled
- loading where actions wait on network/agent state
- error where validation or API failure is possible
- empty where collections can be empty
- selected/current where navigation or choices exist

## Chat State Contract

The chat surface must demonstrate:

- new conversation state
- active conversation with history
- long user and assistant messages
- code block/result card
- agent activity/timeline card
- permission request card
- model/context/permission indicators
- composer ready/disabled/submitting states

## Admin Overlay Contract

- Admin surfaces open as a console, modal, or panel layered over the chat-centered shell.
- Overlay close returns the user to the prior chat context.
- Direct navigation to an admin route may open the same overlay over the default chat shell.
- Forms with destructive or sensitive actions require explicit confirmation or clear impact copy.
- Loading, empty, error, and success states are visible inside the overlay.

## Visual QA Contract

Minimum viewport checks:

- 1366 x 768 notebook
- 1440 x 900 desktop
- 1920 x 1080 wide desktop

Expected results:

- no critical overlap
- no page-level horizontal scroll in chat/admin surfaces
- composer remains reachable
- user menu remains usable
- overlays fit viewport and scroll internally
- text remains readable in dark and light mode
