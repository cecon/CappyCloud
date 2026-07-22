# Data Model: Project-Aware Chat Suggestions

## ProjectSuggestion

Represents one card candidate or active card for a repository/project.

**Fields**

- `id`: UUID, primary identity.
- `repository_id`: UUID, required, references repository.
- `title`: Short Portuguese card title.
- `prompt`: Portuguese prompt inserted into the chat composer.
- `category`: One of `explore`, `build`, `review`, `fix`, `support`, `docs`, `custom`.
- `source`: One of `initial_context`, `question_history`, `manual`.
- `status`: One of `active`, `candidate`, `suppressed`, `stale`, `failed`.
- `priority`: Integer ordering signal, higher wins.
- `safety_state`: One of `passed`, `blocked`, `needs_review`.
- `freshness_state`: One of `fresh`, `stale`, `unknown`.
- `analysis_window_start`: Optional timestamp for history-derived suggestions.
- `analysis_window_end`: Optional timestamp for history-derived suggestions.
- `last_calibrated_at`: Optional timestamp.
- `suppressed_at`: Optional timestamp.
- `suppressed_by`: Optional user id.
- `suppression_reason`: Optional short reason.
- `metadata`: Structured JSON for source counts, document/skill references, and theme labels. Must not contain raw prompts or secret-bearing snippets.
- `created_at`: Timestamp.
- `updated_at`: Timestamp.

**Validation Rules**

- Active suggestions must have non-empty `title` and `prompt`.
- Active suggestions must have `safety_state = passed`.
- A repository should expose at most 4 active suggestions in the user-facing response.
- `prompt` must be concise enough for the current card layout and written in Portuguese.
- `metadata` must not store raw prompt text, author identifiers, or conversation IDs from cross-user history.

**State Transitions**

```text
candidate -> active       when safety and diversity checks pass
candidate -> suppressed   when admin suppresses before publication
active -> suppressed      when admin suppresses after publication
active -> stale           when source context expires or is superseded
stale -> active           when recalibration refreshes and safety passes
candidate/active -> failed when generation or validation cannot complete
```

## SuggestionCalibrationRun

Records one recalibration attempt for a repository/project.

**Fields**

- `id`: UUID, primary identity.
- `repository_id`: UUID, required.
- `trigger`: One of `daily`, `document_changed`, `skill_changed`, `manual`.
- `status`: One of `queued`, `running`, `succeeded`, `failed`, `skipped`.
- `started_at`: Optional timestamp.
- `finished_at`: Optional timestamp.
- `analysis_window_start`: Optional timestamp.
- `analysis_window_end`: Optional timestamp.
- `eligible_message_count`: Count of user messages included after access/safety filters.
- `eligible_user_count`: Count of distinct authorized users included as aggregate signal.
- `suggestions_created`: Count.
- `suggestions_activated`: Count.
- `suggestions_suppressed`: Count.
- `failure_reason`: Sanitized optional text.
- `created_at`: Timestamp.

**Validation Rules**

- Failed runs must store a sanitized failure reason.
- Skipped runs must state why, such as missing project context or duplicate pending recalibration.
- Counts are aggregate only and must not expose message, conversation, or user identity.

## ProjectQuestionPattern

An internal aggregate signal derived from user questions for one repository/project.

**Fields**

- `repository_id`: UUID.
- `theme_key`: Stable normalized label, such as `bug-investigation` or `docs-explanation`.
- `theme_label`: Portuguese display-safe theme label.
- `frequency`: Aggregate count in the analysis window.
- `distinct_user_count`: Aggregate count.
- `last_seen_at`: Timestamp.
- `source_window_start`: Timestamp.
- `source_window_end`: Timestamp.

**Validation Rules**

- Pattern records must not contain raw prompt text.
- Theme labels must be generic enough to avoid customer, secret, incident, or author disclosure.
- Patterns influence priority and diversity but are not displayed as evidence to end users.

## InitialSuggestionProfile

Derived context used to seed suggestions before history-based calibration is available.

**Fields**

- `repository_id`: UUID.
- `repository_name`: Repository display name.
- `repository_slug`: Repository slug.
- `confluence_space`: Optional existing repository metadata.
- `confluence_labels`: Optional existing repository metadata.
- `document_titles`: Active document titles already registered/ingested.
- `skill_titles`: Active skill titles already registered/ingested.
- `skill_summaries`: Short summaries already stored for active project skills.

**Validation Rules**

- Uses only CappyCloud-known metadata, documents, and skills.
- Does not inspect live repository code or depend on sandbox readiness.
- Missing documents/skills degrades to metadata-only suggestions.

## SuggestionVisibilityContext

Runtime context used to decide which cards the current user can see.

**Fields**

- `user_id`: Current user.
- `user_role`: Current role.
- `repository_slug`: Selected project slug.
- `repository_id`: Resolved repository id.
- `has_repository_access`: Boolean.
- `is_empty_chat`: Boolean.
- `selected_branch`: Optional branch.
- `selected_sandbox_id`: Optional sandbox.

**Validation Rules**

- User-facing suggestions require repository access unless the user has an admin role that is explicitly allowed by existing access rules.
- Suggestions are returned for empty-state display only.
- Branch and sandbox are preserved in the composer but do not change suggestion identity in the MVP.

## Relationships

- Repository 1 -> many ProjectSuggestions.
- Repository 1 -> many SuggestionCalibrationRuns.
- SuggestionCalibrationRun may create/update many ProjectSuggestions.
- ProjectQuestionPattern is derived from Message/Conversation history but does not retain raw message identity.
- InitialSuggestionProfile is derived from Repository, Document, and Skill rows.
