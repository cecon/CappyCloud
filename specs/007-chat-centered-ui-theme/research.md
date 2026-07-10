# Research: Chat-Centered UI Theme

## Decision: Use Tailwind CSS v4 through the Vite plugin

**Rationale**: The official Tailwind CSS documentation recommends installing `tailwindcss` and `@tailwindcss/vite`, adding the Vite plugin, and importing Tailwind from CSS for Vite projects. This matches the existing `web/` app, which is already Vite-based.

**External evidence**: Tailwind CSS official docs, "Installing Tailwind CSS as a Vite plugin", document installing `tailwindcss` and `@tailwindcss/vite`, configuring the Vite plugin, and adding `@import "tailwindcss";` in CSS: https://tailwindcss.com/docs/installation/using-vite

**Alternatives considered**:

- Tailwind through PostCSS: rejected because the Vite plugin is the documented seamless path for Vite.
- Keep CSS Modules only: rejected because the clarified requirement requires Tailwind.

## Decision: Use shadcn/ui existing-project setup

**Rationale**: The current frontend is an existing Vite + React + TypeScript app. The official shadcn/ui Vite guide has an "Existing Project" path: add Tailwind, configure `@/*` path aliases in TypeScript/Vite, run `shadcn` init, and add components. This avoids scaffolding a second app.

**External evidence**: shadcn/ui official Vite guide documents existing-project setup, Tailwind install, alias setup, Vite config changes, `pnpm dlx shadcn@latest init`, and adding components: https://ui.shadcn.com/docs/installation/vite

**Alternatives considered**:

- `pnpm dlx shadcn@latest init -t vite`: rejected because it scaffolds a new Vite project, while CappyCloud already has one.
- Manual component copy without shadcn config: rejected because it increases drift and makes future component additions harder.

## Decision: Target Tailwind v4-compatible shadcn components

**Rationale**: The app already uses React 19. shadcn/ui notes that new projects start with Tailwind v4 and React 19, and its Tailwind v4 guide describes CSS variable updates, `@theme inline`, dependency updates, and `tw-animate-css` replacing the older animation plugin.

**External evidence**: shadcn/ui Tailwind v4 docs describe React 19/Tailwind v4 compatibility, CSS variable handling, dependency updates, and `tw-animate-css`: https://ui.shadcn.com/docs/tailwind-v4

**Alternatives considered**:

- Tailwind v3 compatibility mode: rejected because the project is a fresh Tailwind adoption and should not start from legacy config.
- Mixed v3/v4 config: rejected because it complicates theming and future component generation.

## Decision: Replace Mantine for authenticated surfaces instead of wrapping it

**Rationale**: The clarified spec says the redesigned authenticated frontend must use shadcn/ui and Tailwind as the component and theming foundation. Keeping Mantine as the visible base would fail that requirement and preserve two component systems on the primary product surface.

**Repository evidence**: `web/package.json` currently depends on `@mantine/core`, `@mantine/form`, and `@mantine/hooks`; `web/src/main.tsx` wraps the app in `MantineProvider`; many pages import Mantine components. The migration therefore needs explicit dependency and component replacement tasks.

**Alternatives considered**:

- Keep Mantine and only mimic the reference theme: rejected by clarification.
- Hybrid Mantine + shadcn: rejected because it creates two UI foundations and risks inconsistent theme behavior across the all-screens migration.

## Decision: Preserve existing backend/API and authorization contracts

**Rationale**: The feature is a frontend redesign. Authorization, repository visibility, model access, sandbox access, and admin/super-admin checks must remain enforced by current guards and backend behavior. The UI may hide unavailable options, but it must not become the authorization boundary.

**Repository evidence**: `web/src/App.tsx` uses `ProtectedPage`, `RequireAdmin`, and `RequireSuperAdmin`; `web/src/components/AppLayout.tsx` filters nav items by admin/super-admin state. These concepts must be preserved in the new user menu and admin overlay routing.

**Alternatives considered**:

- Collapse all authorization into menu visibility: rejected because the spec and constitution require real authorization boundaries.
- Change backend contracts now: rejected because no missing backend capability is known at planning time.

## Decision: Use `tmp/Cappy` as visual reference, not a source artifact

**Rationale**: The local reference package contains HTML, screenshots, logo/assets, and UX states. It should guide layout, tokens, density, and states, but should not be committed wholesale or used as generated production code.

**Repository evidence**: `tmp/Cappy/CappyCloud.dc.html` includes the chat-centered concept, theme variables, admin console overlays, user/admin/model/MCP states, and many screenshots under `tmp/Cappy/screenshots/`.

**Alternatives considered**:

- Copy generated HTML into React: rejected because it bypasses project structure, typing, route guards, API integration, and maintainability.
- Ignore reference and redesign from scratch: rejected because the spec explicitly points to `tmp/Cappy`.
