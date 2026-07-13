# Feature Specification: Persistent User Workspaces

**Feature Branch**: `[006-persistent-user-workspaces]`

**Created**: 2026-07-08

**Status**: Draft

**Input**: User description: "We share the sandbox between users and isolate by worktree. Persist this by user so the system does not create a new worktree for the same user every time."

## Clarifications

### Session 2026-07-08

- Q: What should happen when a persistent user baseline workspace is dirty because a previous operation ended unexpectedly?-> A: Repair automatically by discarding uncommitted baseline changes before the agent relies on it.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Reuse My Prepared Repository Workspace (Priority: P1)

As a user who repeatedly opens conversations for the same selected repository, I want the system to reuse my prepared repository workspace so that new conversations start quickly without recreating the same baseline worktree every time.

**Why this priority**: This directly removes the repeated setup delay and visual noise that users experience when the same sandbox/repository is used across multiple conversations.

**Independent Test**: Can be tested by selecting a repository, starting one conversation, then starting another conversation for the same user and repository. The second conversation should be ready without repeating full repository workspace preparation.

**Acceptance Scenarios**:

1. **Given** a user has already used a repository in the shared sandbox, **When** the same user starts a new conversation for that repository, **Then** the system reuses that user's prepared repository workspace as the baseline.
2. **Given** the same shared sandbox is used by multiple users, **When** two users select the same repository, **Then** each user receives an isolated workspace baseline that cannot expose another user's uncommitted files or runtime state.

---

### User Story 2 - Keep Editing Sessions Isolated (Priority: P2)

As a user running an agent that may edit files or prepare a pull request, I want each editing task to remain isolated so that exploratory or parallel conversations do not corrupt each other.

**Why this priority**: Reusing workspaces must not weaken the safety guarantees that protect conversations, branches, and repository state.

**Independent Test**: Can be tested by running two conversations for the same user and repository where one conversation changes files. The other conversation should not see those changes unless the user intentionally carries them forward through an approved workflow.

**Acceptance Scenarios**:

1. **Given** a user has a persistent workspace for a repository, **When** a conversation enters an editing or pull-request-producing flow, **Then** the system creates or uses an isolated task workspace for those changes.
2. **Given** two active conversations for the same user and repository, **When** one conversation modifies files, **Then** the other conversation's baseline remains unchanged.

---

### User Story 3 - Recover and Reuse Safely (Priority: P3)

As a user returning after a sandbox restart or workspace cleanup, I want the system to recover or recreate my workspace without requiring manual cleanup.

**Why this priority**: Persistent workspaces reduce repeated setup, but they must remain reliable when volumes are pruned, repositories change branches, or the sandbox is restarted.

**Independent Test**: Can be tested by deleting or invalidating a user's prepared workspace and starting a new conversation for the same repository. The system should recreate the workspace and continue with a clear status.

**Acceptance Scenarios**:

1. **Given** a recorded user workspace no longer exists in the sandbox, **When** the user starts a conversation that needs it, **Then** the system recreates the workspace and updates its recorded state.
2. **Given** repository access has been revoked for a user, **When** that user starts a conversation for the repository, **Then** the system denies workspace reuse or creation.

---

### Edge Cases

- A user changes the selected base branch for a repository after a workspace already exists.
- The persistent workspace exists but is dirty because a previous operation ended unexpectedly.
- A dirty persistent workspace is automatically repaired by discarding uncommitted baseline changes before a new conversation relies on it.
- A repository is deactivated, deleted, or its clone URL changes after user workspaces exist.
- The shared sandbox volume is pruned while workspace records still exist.
- Two browser tabs for the same user start conversations for the same repository at the same time.
- A conversation is read-only at first and later requests edits or a pull request.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST maintain a persistent prepared repository workspace per user, repository, and selected base branch.
- **FR-002**: System MUST reuse the user's prepared workspace as the baseline for new conversations that select the same repository and base branch.
- **FR-003**: System MUST keep persistent workspaces isolated between users, even when they share the same sandbox container and repository catalog entry.
- **FR-004**: System MUST keep editing, pull-request, and other mutating flows isolated from the persistent prepared workspace unless the user explicitly promotes or accepts changes into a follow-up workflow.
- **FR-005**: System MUST detect when a recorded persistent workspace is missing or unhealthy and recreate or repair it automatically before the agent relies on it.
- **FR-006**: System MUST enforce existing repository authorization before creating, reusing, or exposing any user workspace.
- **FR-007**: System MUST handle concurrent attempts to prepare the same user/repository/base-branch workspace without producing duplicate conflicting workspaces.
- **FR-008**: System MUST show users clear session preparation status that distinguishes reusing an existing workspace from creating or repairing one.
- **FR-009**: System MUST preserve existing conversation history and task isolation semantics when persistent workspaces are introduced.
- **FR-010**: System MUST provide a cleanup path for stale persistent workspaces without deleting active conversation workspaces.
- **FR-011**: System MUST repair dirty persistent baseline workspaces by discarding uncommitted baseline changes before deriving any conversation workspace from them.

### Key Entities *(include if feature involves data)*

- **User Repository Workspace**: A user's persistent prepared workspace for a repository and base branch. Tracks owner, repository, base branch, sandbox, path, health/status, last use, and creation metadata.
- **Conversation Workspace**: The per-conversation or per-task isolated workspace used when a conversation needs mutation isolation, review, or pull-request preparation.
- **Workspace Health State**: The observable readiness of a user workspace, including ready, preparing, repairing, missing, dirty, unauthorized, and error states.

### Runtime Context, Security & Evidence *(mandatory when applicable)*

- **RC-001**: Repository selection, selected model, skills, MCP configuration, and external documentation remain runtime context and must continue to come from conversation, database, or UI configuration.
- **RC-002**: Existing repository authorization rules remain mandatory. A user workspace must never bypass repository visibility or cross-user isolation.
- **RC-003**: No external documentation is required to define this behavior; repository evidence reviewed includes `docs/decisions/adr-002-sandbox-runtime-and-worktree-sessions.md`, `services/cappycloud_agent/_environment_manager.py`, and `services/sandbox/session_server.js`.
- **RC-004**: Sandbox and Git behavior is in scope. The feature changes workspace lifecycle semantics in the shared sandbox and must explicitly avoid cross-user leakage, dirty baseline reuse, and accidental branch contamination.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For a repeat conversation using the same user, repository, and base branch, visible repository preparation completes at least 70% faster than the first preparation in normal local testing.
- **SC-002**: In a two-user test using the same repository, neither user can observe the other user's uncommitted files or workspace path contents.
- **SC-003**: In a parallel conversation test for the same user and repository, changes made by one mutating conversation do not appear in the other conversation unless explicitly promoted through an approved workflow.
- **SC-004**: If a recorded workspace is deleted from the sandbox, the next conversation recreates it automatically and reaches a usable state without manual intervention.
- **SC-005**: At least 95% of new conversations for already prepared user/repository/base-branch combinations avoid full workspace creation during normal operation.

## Assumptions

- The first implementation keeps one shared sandbox container model and improves workspace persistence inside it rather than introducing one container per user.
- Persistent workspaces are intended as prepared baselines, not as shared mutable task directories.
- Conversation-level worktrees or equivalent isolated directories remain required for flows that modify files, prepare diffs, push branches, or create pull requests.
- Existing repository access controls and sandbox path guards remain the source of truth for authorization and filesystem boundaries.
- Cleanup can initially be policy-driven by age/status and does not need a user-facing cleanup UI in the first release.
