# Data Model: Chat-Centered UI Theme

This feature does not introduce persisted backend data. The model below describes UI state, theme contracts, and route-level entities needed to implement and validate the redesign.

## Theme

**Purpose**: Defines the visual language for every authenticated screen.

**Fields**:

- `mode`: `dark` or `light`.
- `colors`: semantic color variables for background, foreground, surfaces, borders, accent, success, warning, danger, muted text, and focus.
- `radius`: component radius scale, capped to compact product UI needs.
- `spacing`: density scale for chat, menus, admin panels, forms, and tables.
- `typography`: sans and mono font families plus text scale.
- `states`: default, hover, active, focus-visible, disabled, loading, error, empty, selected.

**Validation rules**:

- Every interactive component must expose focus-visible styling.
- Dark and light modes must support readable contrast for primary/secondary text and status states.
- Tokens live in CSS/theme configuration, not ad hoc component literals.

## Chat Layout

**Purpose**: Primary authenticated workspace centered on conversation.

**Fields**:

- `conversationList`: visible support rail for recent/current conversations.
- `activeConversation`: selected conversation or new-chat state.
- `contextBar`: workspace, repository/context, sandbox state, collaborators/presence, selected model, permission mode.
- `messageStream`: user messages, assistant messages, code blocks, tool/activity cards, permission requests, result cards.
- `composer`: prompt input, send action, permission selector, attachment/context indicators where supported.
- `supportRail`: activity/timeline rail from the reference template when applicable.

**Validation rules**:

- The current duplicated two-sidebar chat layout must not remain.
- Composer must remain reachable during long message streams.
- Chat content must not force horizontal page scrolling.

## User Menu

**Purpose**: Account-centered entry point for secondary navigation and role-based administration.

**Fields**:

- `profileSummary`: user identity and role label.
- `preferences`: theme mode and account preferences.
- `primaryActions`: new conversation, password/account actions, sign out.
- `adminActions`: admin/super-admin entries allowed for the current user.
- `utilityActions`: settings, runs, analytics, skills, MCP, or other authenticated secondary views.

**Validation rules**:

- Non-admin users must not see admin-only actions.
- Super-admin-only actions must remain hidden from regular admins.
- Menu visibility is not the only authorization layer; route/backend guards remain required.

## Administrative Area

**Purpose**: Workspace management presented as a console, modal, or panel layered over the chat-centered shell.

**Fields**:

- `section`: dashboard, users, sandboxes, repositories, MCP servers, skills, models, providers, runs, analytics where applicable.
- `permissionLevel`: user, admin, or super-admin.
- `contentState`: loading, loaded, empty, error, saving.
- `actions`: create, edit, delete, test, sync, grant access, revoke access, promote/demote, view details, confirm/cancel.

**Validation rules**:

- Admin areas must open over the chat-centered experience according to the `tmp/Cappy` reference.
- Sensitive actions must communicate impact and result.
- Existing admin entry points must remain reachable to authorized users.

## Route Coverage

**Purpose**: Ensures every authenticated route is accounted for in the redesign.

**Routes**:

- `/`
- `/chat`
- `/runs`
- `/analytics`
- `/skills`
- `/mcp`
- `/settings`
- `/change-password`
- `/admin/users`
- `/admin/sandboxes`
- `/admin/repositories`
- `/admin/skills-global`
- `/admin/models`
- `/admin/providers`

**Validation rules**:

- No route above may retain the previous visual language.
- Admin routes may be implemented as routed overlays, modal routes, or shell state, but direct URL access must still land in an authorized redesigned experience.
- Redirects such as `/register`, `/environments`, and `/admin/agents-global` must continue to resolve predictably.

## Design Reference

**Purpose**: Local source of visual intent.

**Fields**:

- `htmlReference`: `tmp/Cappy/CappyCloud.dc.html`
- `screenshots`: `tmp/Cappy/screenshots/*.png`
- `brandAssets`: `tmp/Cappy/assets/capybara.png` and `tmp/Cappy/uploads/Capybara.svg`

**Validation rules**:

- Reference assets inform design decisions but are not copied blindly as production code.
- Any committed brand asset must be intentionally placed under `web/src/assets/` or `web/public/` with an implementation reason.
