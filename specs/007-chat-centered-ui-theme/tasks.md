# Tasks: Chat-Centered UI Theme

**Input**: Design documents from `specs/007-chat-centered-ui-theme/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/ui-contract.md](contracts/ui-contract.md), [quickstart.md](quickstart.md)

**Tests**: No dedicated frontend test runner is currently declared in `web/package.json`; validation is planned through focused implementation checks, route smoke checks, `pnpm run lint`, and `pnpm run build`.

**Organization**: Tasks are grouped by user story so each story can be implemented and validated independently after the shared foundation is complete.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Align project governance and install the new frontend foundation required by the clarified spec.

- [X] T001 Update `.specify/memory/constitution.md` to authorize the approved shadcn/ui + Tailwind authenticated frontend foundation through the Spec Kit governance path
- [X] T002 Update `.agents/skills/frontend-implementation/SKILL.md` to describe the approved shadcn/ui + Tailwind workflow for this frontend migration
- [X] T003 [P] Update `.agents/skills/design-system/SKILL.md` with Tailwind/shadcn token guidance for CappyCloud
- [X] T004 [P] Update `.agents/skills/ux-design/SKILL.md` so UX decisions for this feature no longer assume Mantine-only components
- [X] T005 Update `web/package.json` with Tailwind v4, shadcn/ui, Radix/shadcn support packages, `lucide-react`, `clsx`, `tailwind-merge`, `class-variance-authority`, and `tw-animate-css`
- [X] T006 Update `web/pnpm-lock.yaml` and `web/package-lock.json` from the dependency changes in `web/package.json`
- [X] T007 Configure Tailwind Vite plugin and `@/*` alias in `web/vite.config.ts`
- [X] T008 Configure `@/*` alias in `web/tsconfig.json` and `web/tsconfig.app.json`
- [X] T009 Add shadcn configuration in `web/components.json`
- [X] T010 Create shadcn utility helper in `web/src/lib/utils.ts`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Establish reusable theme, primitives, layout data, and compatibility boundaries before any user-story implementation.

**Critical**: No user story work should start until this phase is complete.

- [ ] T011 Replace Mantine global theme wiring with Tailwind/shadcn globals in `web/src/main.tsx`
- [X] T012 Define CappyCloud dark/light CSS variables, Tailwind theme mappings, scrollbar styling, and base layers in `web/src/index.css`
- [X] T013 Add initial shadcn primitives in `web/src/components/ui/button.tsx`, `web/src/components/ui/dropdown-menu.tsx`, `web/src/components/ui/dialog.tsx`, `web/src/components/ui/sheet.tsx`, `web/src/components/ui/tabs.tsx`, `web/src/components/ui/input.tsx`, `web/src/components/ui/textarea.tsx`, `web/src/components/ui/select.tsx`, `web/src/components/ui/badge.tsx`, `web/src/components/ui/card.tsx`, `web/src/components/ui/table.tsx`, `web/src/components/ui/tooltip.tsx`, `web/src/components/ui/scroll-area.tsx`, and `web/src/components/ui/skeleton.tsx`
- [X] T014 Create route and menu metadata for all authenticated routes in `web/src/components/layout/navigation.ts`
- [X] T015 Create role-aware navigation helpers for user/admin/super-admin visibility in `web/src/components/layout/navigation.ts`
- [X] T016 Create reusable loading, empty, error, and forbidden state components in `web/src/components/layout/AppStates.tsx`
- [X] T017 Create shared overlay shell components in `web/src/components/layout/AppOverlay.tsx`
- [X] T018 Create shared admin console shell components in `web/src/components/admin/AdminConsole.tsx`
- [X] T019 Create a route coverage checklist module for authenticated routes in `web/src/components/layout/routeCoverage.ts`
- [X] T020 Copy or intentionally place the approved CappyCloud brand asset from `tmp/Cappy` into `web/src/assets/cappycloud-mark.png` or document the existing public asset reuse in `web/src/components/layout/BrandMark.tsx`
- [X] T021 Remove direct Material Symbols/Tabler-only assumptions from shared layout icon usage by introducing lucide icon mapping in `web/src/components/layout/icons.tsx`

**Checkpoint**: Tailwind/shadcn foundation builds, shared layout primitives exist, and every authenticated route is represented in metadata.

---

## Phase 3: User Story 1 - Conversar Como Experiencia Central (Priority: P1) MVP

**Goal**: Deliver the primary chat-centered experience with the `tmp/Cappy` support rails, context bar, message stream, activity/permission cards, and composer.

**Independent Test**: Log in, open `/chat`, start/select a conversation, send a message, and confirm the chat is central, the composer remains reachable, context is visible, and the current duplicated two-sidebar layout is gone.

### Implementation for User Story 1

- [X] T022 [US1] Replace the global sidebar shell with a chat-centered authenticated shell in `web/src/components/AppLayout.tsx`
- [X] T023 [P] [US1] Implement conversation history/support rail in `web/src/components/chat/ConversationRail.tsx`
- [X] T024 [P] [US1] Implement context bar for workspace, repository/context, sandbox, collaborators, model, and permission mode in `web/src/components/chat/ChatContextBar.tsx`
- [X] T025 [P] [US1] Implement message bubble and markdown/code styling in `web/src/components/chat/ChatMessage.tsx`
- [ ] T026 [P] [US1] Migrate tool/activity display from `web/src/components/ToolCallCard.tsx` and `web/src/components/MessageTimeline.tsx` into `web/src/components/chat/AgentActivityCard.tsx`
- [X] T027 [P] [US1] Migrate permission request UI from `web/src/components/ActionRequiredCard.tsx` into `web/src/components/chat/PermissionRequestCard.tsx`
- [X] T028 [P] [US1] Implement chat composer with permission selector, send state, and overflow-safe layout in `web/src/components/chat/ChatComposer.tsx`
- [ ] T029 [US1] Recompose `web/src/pages/ChatPage.tsx` with `ConversationRail`, `ChatContextBar`, message stream, activity cards, permission cards, and `ChatComposer`
- [ ] T030 [US1] Remove or retire duplicated chat side menu behavior from `web/src/components/chat.module.css`
- [ ] T031 [US1] Ensure attachment, file explorer, diff, thinking, and document panels still render in the new chat surface by migrating `web/src/components/AttachmentTray.tsx`, `web/src/components/FileExplorer.tsx`, `web/src/components/DiffViewer.tsx`, `web/src/components/ThinkingStream.tsx`, and `web/src/components/DocumentsPanel.tsx`
- [ ] T032 [US1] Validate `/chat` manually against `specs/007-chat-centered-ui-theme/quickstart.md` scenario 1

**Checkpoint**: User Story 1 is independently demoable as the MVP.

---

## Phase 4: User Story 2 - Acessar Funcoes Secundarias Pelo Menu Do Usuario (Priority: P2)

**Goal**: Move secondary navigation, preferences, account actions, and allowed admin entries into the user menu while preserving route guards.

**Independent Test**: Open the user menu as regular user, admin, and super-admin; verify each sees only permitted entries and can reach the expected redesigned route or overlay.

### Implementation for User Story 2

- [X] T033 [US2] Implement account-centered user menu in `web/src/components/layout/UserMenu.tsx`
- [X] T034 [US2] Integrate `UserMenu` into `web/src/components/AppLayout.tsx`
- [X] T035 [P] [US2] Add theme preference control and persistence in `web/src/components/layout/ThemeToggle.tsx`
- [X] T036 [P] [US2] Add account actions for change password and logout in `web/src/components/layout/UserMenu.tsx`
- [X] T037 [US2] Move secondary route links for runs, analytics, agentic delivery, skills, MCP, and settings from the old sidebar metadata into `web/src/components/layout/navigation.ts`
- [X] T038 [US2] Move admin/super-admin entries for users, sandboxes, repositories, global skills, models, and providers into role-aware user menu groups in `web/src/components/layout/navigation.ts`
- [X] T039 [US2] Preserve anonymous, `must_change_password`, admin, and super-admin guard behavior in `web/src/App.tsx`
- [ ] T040 [US2] Remove obsolete sidebar group rendering from `web/src/components/app-layout.module.css`
- [ ] T041 [US2] Validate user/admin/super-admin menu visibility manually against `specs/007-chat-centered-ui-theme/quickstart.md` scenarios 2 and 5

**Checkpoint**: User Story 2 is independently testable through the user menu and direct protected URLs.

---

## Phase 5: User Story 3 - Aplicar Tema Unificado Em Todas As Telas (Priority: P2)

**Goal**: Apply the shadcn/Tailwind theme and shared states across every authenticated route and public-adjacent account surface.

**Independent Test**: Visit every authenticated route from `contracts/ui-contract.md`, toggle theme when available, and confirm no authenticated screen retains the previous visual language.

### Implementation for User Story 3

- [ ] T042 [US3] Migrate dashboard/start route styling from `web/src/pages/DashboardPage.tsx` and `web/src/components/dashboard/` to Tailwind/shadcn components
- [ ] T043 [P] [US3] Migrate runs UI from `web/src/pages/RunsPage.tsx` and `web/src/pages/runs.module.css`
- [ ] T044 [P] [US3] Migrate analytics UI from `web/src/pages/AnalyticsPage.tsx` and `web/src/pages/analytics.module.css`
- [ ] T045 [P] [US3] Migrate agentic delivery UI from `web/src/pages/AgenticDeliveryPage.tsx`, `web/src/pages/agentic-delivery-page.module.css`, and `web/src/components/agentic-delivery/`
- [ ] T046 [P] [US3] Migrate skills UI from `web/src/pages/SkillsPage.tsx` and `web/src/components/SkillsPageSections.tsx`
- [ ] T047 [P] [US3] Migrate MCP user UI from `web/src/pages/McpServerPage.tsx`, `web/src/pages/mcp-server.module.css`, and `web/src/components/UserMcpServerCard.tsx`
- [ ] T048 [P] [US3] Migrate settings UI from `web/src/pages/SettingsPage.tsx` and `web/src/pages/settings.module.css`
- [ ] T049 [P] [US3] Migrate change password UI from `web/src/pages/ChangePasswordPage.tsx`
- [ ] T050 [P] [US3] Align public-adjacent login page visual language with the new theme in `web/src/pages/LoginPage.tsx`
- [ ] T051 [US3] Remove Mantine imports from migrated authenticated components under `web/src/pages/` and `web/src/components/`
- [ ] T052 [US3] Remove obsolete Mantine package dependencies from `web/package.json` and remove unused CSS module files only after all migrated files compile
- [ ] T053 [US3] Validate all routes in `specs/007-chat-centered-ui-theme/contracts/ui-contract.md` against `specs/007-chat-centered-ui-theme/quickstart.md` scenario 4

**Checkpoint**: User Story 3 covers theme consistency across all authenticated screens.

---

## Phase 6: User Story 4 - Preservar Gestao Administrativa No Novo Layout (Priority: P3)

**Goal**: Preserve all administrative workflows in console/modal/panel overlays layered over the chat-centered experience.

**Independent Test**: As admin/super-admin, open each admin entry from the user menu and direct URL, confirm the overlay pattern, and execute at least one allowed read and one allowed mutation where the current product supports it.

### Implementation for User Story 4

- [X] T054 [US4] Implement routed admin overlay behavior in `web/src/components/admin/AdminOverlayRouter.tsx`
- [X] T055 [US4] Wire admin overlay routing into `web/src/App.tsx` while preserving direct admin URL access
- [ ] T056 [P] [US4] Migrate users admin UI from `web/src/pages/AdminUsersPage.tsx` and `web/src/components/UserAccessDrawer.tsx` into admin console components
- [ ] T057 [P] [US4] Migrate sandboxes admin UI from `web/src/pages/AdminSandboxesPage.tsx`, `web/src/components/SandboxGlobalsDrawer.tsx`, and `web/src/components/sandbox-globals/`
- [ ] T058 [P] [US4] Migrate repositories admin UI from `web/src/pages/AdminRepositoriesPage.tsx` and `web/src/components/RepositoryDocumentsModal.tsx`
- [ ] T059 [P] [US4] Migrate global skills admin UI from `web/src/pages/AdminGlobalSkillsPage.tsx`
- [ ] T060 [P] [US4] Migrate model catalog admin UI from `web/src/pages/AdminModelsPage.tsx` and `web/src/components/AiModelsPanel.tsx`
- [ ] T061 [P] [US4] Migrate providers admin UI from `web/src/pages/AdminProvidersPage.tsx`
- [ ] T062 [P] [US4] Migrate MCP admin forms from `web/src/components/McpConnectionPanel.tsx`, `web/src/components/McpServerFormModal.tsx`, and `web/src/components/McpTokenModal.tsx`
- [ ] T063 [US4] Ensure destructive/sensitive admin actions use explicit confirmation and clear outcome messaging in `web/src/components/admin/AdminConsole.tsx`
- [ ] T064 [US4] Validate admin overlays manually against `specs/007-chat-centered-ui-theme/quickstart.md` scenario 3

**Checkpoint**: User Story 4 preserves administrative capability in the new overlay model.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Verification, cleanup, accessibility, and documentation across the full redesign.

- [ ] T065 [P] Audit `web/src/` for remaining `@mantine/` imports and either remove them or document intentional non-authenticated exceptions
- [ ] T066 [P] Audit `web/src/` for remaining old CSS modules that are no longer imported and remove obsolete files
- [ ] T067 [P] Audit `web/src/` for hardcoded colors outside token definitions and replace with semantic Tailwind/theme variables
- [ ] T068 Verify keyboard focus, `aria-label`, and menu/dialog focus behavior across `web/src/components/layout/`, `web/src/components/chat/`, and `web/src/components/admin/`
- [ ] T069 Verify no page-level horizontal scroll and no critical overlap at 1366x768, 1440x900, and 1920x1080 using `specs/007-chat-centered-ui-theme/quickstart.md`
- [ ] T070 Time the primary chat demo path from `specs/007-chat-centered-ui-theme/quickstart.md` scenario 1 and record whether SC-001 and SC-006 pass
- [ ] T071 Validate dark/light contrast for primary text, secondary text, buttons, selected states, error states, and focus states using `specs/007-chat-centered-ui-theme/quickstart.md`
- [X] T072 Run `pnpm run lint` in `web/`
- [X] T073 Run `pnpm run build` in `web/`
- [ ] T074 Document any validation gaps or skipped checks in `specs/007-chat-centered-ui-theme/quickstart.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on Setup; blocks all user stories.
- **User Story 1 (Phase 3)**: Depends on Foundation and delivers MVP.
- **User Story 2 (Phase 4)**: Depends on Foundation; can run after or alongside US1 once shell integration boundaries are coordinated.
- **User Story 3 (Phase 5)**: Depends on Foundation; should start after the theme primitives are stable and can proceed by route in parallel.
- **User Story 4 (Phase 6)**: Depends on Foundation and benefits from US2 user-menu routing; admin page migrations can proceed in parallel.
- **Polish (Phase 7)**: Depends on all desired user stories.

### User Story Dependencies

- **US1**: No dependency on other stories after Foundation; recommended MVP.
- **US2**: No functional dependency on US1, but both touch `AppLayout`; coordinate file ownership.
- **US3**: Can migrate routes independently after shared theme primitives exist.
- **US4**: Depends on route/menu decisions from US2 for final entry points, but individual admin panel migrations can begin after Foundation.

### Parallel Opportunities

- T003 and T004 can run in parallel.
- T013 can be split by shadcn primitive file after the dependency setup lands.
- T023 through T028 can run in parallel once chat component props are agreed.
- T043 through T050 can run in parallel because they target different pages.
- T056 through T062 can run in parallel because they target different admin surfaces.
- T065 through T067 can run in parallel during cleanup.

## Parallel Examples

### User Story 1

```text
Task: T023 [US1] Implement conversation history/support rail in web/src/components/chat/ConversationRail.tsx
Task: T024 [US1] Implement context bar in web/src/components/chat/ChatContextBar.tsx
Task: T025 [US1] Implement message bubble in web/src/components/chat/ChatMessage.tsx
Task: T028 [US1] Implement composer in web/src/components/chat/ChatComposer.tsx
```

### User Story 3

```text
Task: T043 [US3] Migrate runs UI in web/src/pages/RunsPage.tsx
Task: T044 [US3] Migrate analytics UI in web/src/pages/AnalyticsPage.tsx
Task: T046 [US3] Migrate skills UI in web/src/pages/SkillsPage.tsx
Task: T049 [US3] Migrate change password UI in web/src/pages/ChangePasswordPage.tsx
```

### User Story 4

```text
Task: T056 [US4] Migrate users admin UI in web/src/pages/AdminUsersPage.tsx
Task: T057 [US4] Migrate sandboxes admin UI in web/src/pages/AdminSandboxesPage.tsx
Task: T060 [US4] Migrate model catalog admin UI in web/src/pages/AdminModelsPage.tsx
Task: T061 [US4] Migrate providers admin UI in web/src/pages/AdminProvidersPage.tsx
```

## Implementation Strategy

### MVP First

1. Complete Phase 1 and Phase 2.
2. Complete Phase 3 (US1).
3. Validate `/chat` with quickstart scenario 1.
4. Demo the chat-centered shell before migrating every secondary surface.

### Incremental Delivery

1. Setup + Foundation.
2. US1: chat-centered MVP.
3. US2: user menu and role-aware navigation.
4. US3: all authenticated routes themed.
5. US4: admin console overlays.
6. Polish and gates.

### Risk Control

- Stop before implementation if T001-T004 cannot be resolved, because coding shadcn/Tailwind requires the Spec Kit governance alignment defined by constitution v1.1.0.
- Keep backend contracts unchanged unless a route cannot render with current API data.
- Do not commit `tmp/Cappy` wholesale; only intentional brand assets may move into `web/src/assets/` or `web/public/`.
