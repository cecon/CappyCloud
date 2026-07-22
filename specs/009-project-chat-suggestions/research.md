# Research: Project-Aware Chat Suggestions

## Decision: Initial suggestions use known project context only

**Rationale**: The spec requires cards to appear as soon as a project is selected. The existing workspace API already exposes repository identity and integration metadata, while `skills` and `documents` store registered/ingested project knowledge. Using those sources avoids blocking the empty state on sandbox readiness or code analysis.

**Alternatives considered**:

- Analyze repository code on project selection: rejected because the spec explicitly excludes real-time repository analysis for initial display and this would add latency/sandbox coupling.
- Use only static global prompts: rejected because it preserves the generic repetitive behavior the feature is meant to replace.
- Crawl external docs on demand: rejected for MVP because external documentation crawling is out of scope and would make latency/failure modes harder to control.

## Decision: Persist suggestions and calibration runs in PostgreSQL

**Rationale**: Suggestions need status, priority, source, freshness, suppression, and calibration metadata. PostgreSQL is already the system of record for repositories, conversations, messages, documents, and skills, and supports access-controlled queries and audit-friendly state.

**Alternatives considered**:

- Frontend-only generation: rejected because it cannot safely aggregate cross-user history or enforce central suppression.
- Redis-only cache: rejected because suggestions and calibration state must survive restarts and be inspectable by maintainers.
- Store on repository rows as JSON: rejected because suggestions have lifecycle, status, and relationships that need their own indexes and tests.

## Decision: Add a dedicated ProjectSuggestionRepository port

**Rationale**: The constitution requires persistence and business rules behind ports/use cases. A dedicated port keeps suggestion storage substitutable and testable alongside SQLAlchemy and in-memory fakes.

**Alternatives considered**:

- Extend MessageRepository: rejected because suggestion lifecycle is not message persistence.
- Query ORM directly in HTTP routers: rejected by architecture rules.
- Reuse Skill repository: rejected because skills are knowledge base items, not user-facing card publication state.

## Decision: Recalibration uses aggregate anonymized history signals

**Rationale**: The user asked to learn from what everyone asks in each project, and clarification chose project-level aggregate anonymized history. The plan will count and classify themes without publishing authors, raw prompts, conversation IDs, or private snippets.

**Alternatives considered**:

- Per-user personalization: rejected because the clarified scope is project-level.
- Raw prompt reuse: rejected by privacy and security requirements.
- Organization-wide aggregation: rejected because clarification chose project-level history for authorized users.

## Decision: No LLM-dependent generation in the MVP

**Rationale**: Deterministic templates from metadata, document titles/summaries, skill titles/summaries, and sanitized theme labels can satisfy the first version while avoiding hidden cost, model selection questions, and provider failure modes. This also keeps suggestion display fast and deterministic.

**Alternatives considered**:

- Call OpenRouter during project selection: rejected because model/cost are conversation context and would create latency/cost for a passive empty state.
- Run a background LLM summarizer during recalibration: deferred. It may improve copy later, but it requires explicit model/cost governance and stronger redaction tests.

## Decision: Daily recalibration plus debounced document/skill triggers

**Rationale**: APScheduler already exists in the API lifespan for recurring jobs. Daily recalibration is enough to keep suggestions fresh, while document/skill changes should schedule a project refresh sooner. Debouncing prevents multiple edits or reingestions from creating redundant work.

**Alternatives considered**:

- Recalculate after every conversation: rejected as excessive and noisy.
- Weekly only: rejected because it reacts too slowly to project usage changes.
- Manual-only: rejected because the spec requires automatic periodic recalibration.

## Decision: User endpoint by repository slug, admin operations by suggestion or repository id

**Rationale**: The chat UI selects workspaces by slug, so the user-facing contract should accept `repo_slug`. Administrative suppression/recalibration benefits from stable UUIDs and explicit status metadata.

**Alternatives considered**:

- Add suggestions to `GET /api/workspaces`: rejected because cards have independent loading/error/staleness behavior and should not slow workspace listing.
- Add suggestions to conversation create: rejected because suggestions exist before a conversation is created and only apply to the empty state.

## Decision: Keep the visible UI in the existing empty-state component

**Rationale**: `ChatPage.tsx` already renders the welcome panel, four quick-action cards, repository selector, branch selector, attachments, and permission controls. Replacing card data there minimizes UX disruption and preserves composer behavior.

**Alternatives considered**:

- Build a new landing page: rejected because this is an authenticated chat empty state, not a marketing surface.
- Show suggestions in active conversations: deferred because the spec scopes only the initial empty state.
