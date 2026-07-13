# Quickstart: Validate Chat-Centered UI Theme

## Prerequisites

- Node/pnpm available for `web/`.
- Backend API available through the existing Vite proxy target or a mocked/dev environment accepted by the team.
- Test users for user, admin, and super-admin roles.

## Install/Build Checks

```powershell
cd D:\projetos\CappyCloud\web
pnpm install
pnpm run lint
pnpm run build
```

Expected:

- dependencies install without lockfile drift beyond intentional shadcn/Tailwind changes
- lint passes
- TypeScript/Vite build passes

## Local Run

```powershell
cd D:\projetos\CappyCloud\web
pnpm run dev
```

Open the Vite URL shown in the terminal, normally `http://localhost:5173`.

## Manual Validation Scenarios

### 1. Primary Chat

1. Log in as a regular authenticated user.
2. Start a timer.
3. Open `/chat`.
4. Start a new conversation.
5. Choose or confirm workspace/repository/sandbox/model context when the UI asks for it.
6. Verify chat is the central surface, with the template-style conversation support rail and no duplicated two-sidebar layout.
7. Send a message and confirm the composer remains reachable while messages/activity render.
8. Stop the timer when the first agent response path is visible.

Expected:

- chat is identifiable as the main product surface within 5 seconds
- the full demo path from opening chat through the first agent response path completes in under 60 seconds
- no horizontal page scroll
- context bar shows workspace/repository/sandbox/model/permission context when available

### 2. User Menu Navigation

1. Open the user menu.
2. Verify account, preferences, theme, secondary navigation, and role-appropriate actions.
3. Confirm non-admin users do not see admin-only actions.

Expected:

- secondary areas are discoverable from the user menu
- unavailable actions are hidden or blocked with clear messaging

### 3. Admin Console Overlay

1. Log in as admin or super-admin.
2. Open user management from the user menu or direct `/admin/users`.
3. Confirm admin opens as console/modal/panel over the chat-centered experience.
4. Repeat for sandboxes, repositories, MCP, skills, models, and providers according to role.

Expected:

- prior chat context remains conceptually present
- close returns to chat context
- existing admin entry points remain reachable

### 4. Theme Coverage

1. Toggle dark/light mode if the UI exposes switching.
2. Visit all authenticated routes listed in `contracts/ui-contract.md`.
3. Check buttons, menus, inputs, tables, cards, badges, modals, overlays, loading, empty, error, selected, disabled, and focus states.

Expected:

- all authenticated screens use the unified theme
- readable contrast in both modes
- no Mantine default visual language remains on authenticated screens

Contrast record:

- primary text passes in dark and light modes
- secondary text passes in dark and light modes
- primary and secondary buttons pass in dark and light modes
- selected, error, disabled, loading, and focus-visible states remain legible

### 5. Authorization Regression

1. As non-admin, attempt direct admin URLs.
2. As admin, attempt super-admin-only URLs where applicable.
3. As anonymous user, attempt authenticated URLs.

Expected:

- redirects/blocks match current behavior
- menu visibility does not become the only authorization layer

### 6. Responsive/Desktop QA

Check these viewport sizes:

- 1366 x 768
- 1440 x 900
- 1920 x 1080

Expected:

- no critical text/control overlap
- overlays scroll internally
- composer remains visible/reachable
- user menu is usable
