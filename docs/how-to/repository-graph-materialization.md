# Repository Graph Materialization

Phase 0 persists the sandbox repository graph in Postgres. Phase 1A adds the
deterministic C# extractor `static_roslyn`; Phase 1B adds the deterministic SQL
extractor `static_sql`; Phase 2A adds `doc_import` for indexed schema documents.
All extractors write into the same graph payload and are materialized in the
same tables.

## Schema

- `graph_nodes`: one deterministic node per repository commit.
  - `id` format: `repo:{repo_id}@{commit_sha}:file:{path}` for files and
    `repo:{repo_id}@{commit_sha}:file:{path}#{symbol_qualified_name}` for
    symbols. If the sandbox returns duplicate symbols with the same file and
    qualified name, later rows append `@{sandbox_id}` to keep the ID unique
    without changing the public graph payload.
  - SQL entities use
    `repo:{repo_id}@{commit_sha}:sql:{path}#{entity_kind}:{qualified_name}`.
    This keeps standalone schema entities separate from JS file nodes that may
    share the same path.
  - Document-imported entities use
    `repo:{repo_id}@{commit_sha}:doc:{document_id}#{kind}:{qualified_name}`.
    Documents are repo-scoped, not commit-versioned; rows are re-emitted for
    each materialized commit by design.
  - `source_extractor` identifies the extractor slice. Current writers are
    `static_js`, `static_roslyn`, `static_sql`, `doc_import`, and `llm_gap`
    for reconciliation edges.
  - `extractor_version` is per extractor. `static_roslyn` is currently
    `0.2.0`, `llm_gap` is `0.2.0`, and the other extractors start at `0.1.0`
    until their schema changes.
  - `attrs` stores the original sandbox JSON row so the API can reconstruct the
    current graph response shape.
- `graph_edges`: one deterministic edge per repository commit.
  - `type` is copied from the sandbox edge.
  - `evidence` contains `file`, `line_start`, `line_end`, `snippet`, plus the
    original sandbox edge.
  - Rows without extractor snippets use `confidence='medium'` and
    `snippet=null`.

## Triggering Materialization

- Admin UI: open Repositorios, use the graph panel, and click
  `Re-materializar graph`.
- API:

```bash
curl -X POST \
  -H "Authorization: Bearer $TOKEN" \
  "https://app.cappyfy.com/api/repositories/$REPO_ID/graph/materialize"
```

- Webhooks: GitHub/GitLab push events on the tracked repository default branch
  enqueue `materialize_repo_graph` in `sandbox_sync_queue`.
- On demand:

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "https://app.cappyfy.com/api/repositories/$REPO_ID/graph?materialized=true"
```

If rows for the resolved commit do not exist, the API returns `202` with
`{ "status": "materializing", "job_id": "..." }`.

## C# Extractor

`static_roslyn` is a .NET 8 CLI at `tools/extractors/csharp/` published into the
sandbox image as `cappy-roslyn-extractor`. The sandbox detects `.cs` files and
invokes:

```bash
cappy-roslyn-extractor --repo /repos/$SLUG --out /tmp/graph.json --paths A.cs,B.cs
```

It emits namespace, class, interface, struct, record, enum, method, property,
field and event nodes. It emits deterministic edges for `defines`, `calls`,
`extends`, `implements`, `references_type`, `throws`, and low-confidence
`references` placeholders for unresolved database references.

`target_external` values beginning with `ref:` are not resolved tables. They are
deterministic hints that Phase 2B can reconcile later. Since
`static_roslyn@0.1.1`, EF placeholders use entity type names, not DbContext
member names:

- `ctx.Users` where `Users` is `DbSet<User>` emits `ref:User`.
- `ctx.Set<Order>()` emits `ref:Order`.
- `ctx.Add(user)` or `ctx.AddRange(orders)` emits the compile-time entity type
  from the argument, when it is concrete.
- SQL string literals still emit the table-like token, for example
  `ref:dbo.Users`.

The extractor deliberately ignores DbContext infrastructure members because
they are not schema entities: `SaveChanges`, `SaveChangesAsync`, `Database`,
`ChangeTracker`, `Model`, `DisposeAsync`, `Dispose`, `OnConfiguring`,
`OnModelCreating`, `Entry`, `Entries`, `Attach`, `AttachRange`, `Detach`,
`Find`, `FindAsync`, `Update`, and `UpdateRange`.

EF detection emits only `info` diagnostics when a typed reference cannot be
made safely:

- `ef_dbset_unresolved_generic`: a `DbSet<T>`/`IDbSet<T>` property exists but
  `T` is unresolved or generic.
- `ef_set_unresolved_generic`: `Set<T>()` uses an unresolved or generic `T`.
- `ef_argument_untyped`: an entity-argument method received `null`, `default`,
  or no useful type.
- `ef_argument_ambiguous`: an entity-argument method received `object`,
  anonymous, generic, primitive, or otherwise ambiguous input.

Rollout after a Roslyn extractor bump:

1. Invalidate only Roslyn rows with `source_extractor='static_roslyn'`.
2. Re-materialize the repository graph.
3. Run reconciliation again. `ref:<EntityName>` values should be materially more
   useful to strict/fuzzy/LLM matching than the older `ref:Set` or
   `ref:SaveChanges` infrastructure noise.

`static_roslyn@0.2.0` also emits explicit EF class-to-table declarations as
`maps_to_table` edges:

- `[Table("tgGerAlmo")]` emits `class Almoxarifado -> table:tgGerAlmo`.
- `[Table("tgGerAlmo", Schema = "dbo")]` emits `table:dbo.tgGerAlmo`.
- `modelBuilder.Entity<Almoxarifado>().ToTable("tgGerAlmo")` emits the same
  edge with `attrs.mapping_source='fluent_on_model_creating'`.
- `IEntityTypeConfiguration<T>` and EF6 `EntityTypeConfiguration<T>` classes
  emit with `attrs.mapping_source='entity_type_configuration'`.

The table placeholder is the literal physical name declared in code. It is not
lowercased, plural-normalized, or reconciled inside Roslyn. Multiple conflicting
declarations are recorded as multiple `maps_to_table` edges and a warning
diagnostic `ef_mapping_conflict`.

## SQL Extractor

`static_sql` is a Python 3.11 CLI at `tools/extractors/sql/` installed into the
sandbox image as `cappy-sql-extractor`. The sandbox detects `.sql` files and
invokes:

```bash
cappy-sql-extractor --repo /repos/$SLUG --out /tmp/graph.json --paths A.sql,B.sql
```

It uses `sqlglot` and emits `sql_file`, `table`, `column`, `view`, `index`,
`constraint`, `stored_procedure`, and `trigger` nodes. It emits deterministic
edges for `defines`, `foreign_key`, `references_table`, and `indexes`.

Dialect resolution order:

1. CLI `--dialect`.
2. Repo config `.cappy/sql.toml` with `dialect = "mysql"`.
3. Heuristic scan of the first five SQL files for dialect-specific tokens such
   as `AUTO_INCREMENT`, `IDENTITY`, `NVARCHAR`, or `SERIAL`.
4. Fallback to `postgres`.

Each file can override the repo dialect with a first-line magic comment:

```sql
-- sqlglot:dialect=mysql
```

Foreign keys that reference tables or columns outside the parsed corpus keep the
edge and set `target_external = "table:{schema}.{table}.{column}"` with
`confidence='medium'`. The extractor deliberately does not create schema nodes,
sequence/domain/type nodes, or operational nodes for standalone `SELECT`,
`INSERT`, `UPDATE`, or `DELETE` statements.

When `static_sql` and `static_roslyn` or `static_js` run on the same repo, there
is no automatic reconciliation in Phase 1B. For example, `static_sql` may create
a real table node for `public.users`, while Roslyn may emit
`target_external = "ref:Users"`. These are not linked yet; that future linking
must be explicit to avoid false positives from name-only matching.

## Document Import Extractor

`doc_import` is a Python CLI at `tools/extractors/doc_import/` installed into the
API image as `cappy-doc-import-extractor`. It reads indexed document chunks from
Postgres, reassembles them in `chunk_index` order, and emits structural graph
nodes without depending on the original uploaded file being present on disk.

The current dispatcher supports one format:

- `markdown_schema_catalog`: markdown schema catalogs with table headers like
  `#### dbo.users (12345 linhas)`, followed by `- PK:` and column lines such as
  ``- `tenant_id` int FK->dbo.tenants.id``.

The extractor emits:

- `document` nodes with `attrs.document_id`, `source_type`, `doc_format`,
  `chunks_count`, and `indexed_at`.
- `table` nodes with `attrs.document_id`, `attrs.chunk_index`, `schema`,
  `row_count_hint`, `doc_format`, and `case_preserved`.
- `column` nodes with `attrs.document_id`, `attrs.chunk_index`, `data_type`,
  `is_nullable`, `is_primary_key`, `doc_format`, and `case_preserved`.
- `defines` edges for document-to-table and table-to-column.
- `foreign_key` edges for documented FKs. If the referenced column is absent
  from the same parsed document, the edge is retained as
  `target_external = "table:{schema}.{table}.{column}"` with
  `confidence='medium'`.

Edge metadata specific to the document source is stored under
`graph_edges.evidence->'attrs'`, because `graph_edges` does not have a separate
`attrs` column in Phase 0.

`doc_import` runs in three places:

- During repository graph materialization, for all indexed markdown documents
  linked to the repo.
- After document indexing or re-indexing, via `doc_import_for_document` in
  `sandbox_sync_queue`.
- Manually through the admin endpoint:

```bash
curl -X POST \
  -H "Authorization: Bearer $TOKEN" \
  "https://app.cappyfy.com/api/repositories/$REPO_ID/documents/$DOCUMENT_ID/reimport-graph"
```

The admin graph panel shows `Re-importar schema` when the repository has at
least one indexed markdown document that can be parsed by this extractor.

To add another document parser later, keep the same `source_extractor` value
(`doc_import`) and add an internal dispatcher branch with:

1. A deterministic `detect` rule.
2. A parser that emits the same `{ nodes, edges, diagnostics }` shape.
3. Diagnostics for skipped or ambiguous lines instead of invented schema facts.

There is still no automatic reconciliation in Phase 2A. `doc_import` may create
`table:dbo.Users`, while Roslyn may keep `target_external='ref:Users'`; these
remain separate until Phase 2B performs evidence-based linking.

## LLM Reconciliation (`llm_gap`)

Phase 2B adds a reconciliation layer named `llm_reconciliation`, persisted with
`source_extractor='llm_gap'`. It reads Roslyn edges where
`target_external LIKE 'ref:%'` and `maps_to_table` edges where
`target_external LIKE 'table:%'`, then creates new `resolves_to` edges to
concrete `table` or `column` nodes produced by `doc_import` or `static_sql`.

This phase never mutates or deletes the original `static_roslyn` rows. The raw
placeholder stays available for audit, while `resolves_to` records the resolved
schema anchor.

The cascade is:

1. Strict match for `ref:*`: exact normalized name match, including simple singular/plural
   collapse. It only resolves automatically when there is exactly one candidate,
   the normalized name has at least four characters, and the name is not in the
   generic blocklist (`user`, `item`, `entity`, `dto`, `viewmodel`, etc.).
2. Strict match for `table:*`: schema-aware exact physical table matching. It
   does not use plural collapse, minimum length, or the generic blocklist. If
   the placeholder includes schema, schema and table must both match
   case-insensitively; without schema, exactly one candidate table name must
   match across all schemas.
3. Fuzzy + embedding: ranks up to five candidates using 50% normalized
   Levenshtein score and 50% cosine similarity between the Roslyn evidence
   snippet embedding and the schema chunk embedding. It resolves without LLM
   only when the top score is at least `0.85` and the gap to the second
   candidate is at least `0.15`.
4. LLM decision: with `--mode=all`, the model receives only the C# evidence and
   fixed top-K candidates. It must choose one candidate or return `none`; it is
   not allowed to invent schema entities.

All `resolves_to` edges carry audit attributes under
`graph_edges.evidence->'attrs'`:

- `original_edge_key`: `sha256(repo_id || ':' || commit_sha || ':' || source_id
  || ':' || target_external || ':' || type)`.
- `original_target_external`: the raw Roslyn placeholder, for example
  `ref:Users` or `table:dbo.tgGerAlmo`.
- `placeholder_kind`: `ref_entity` for entity refs or `table_physical` for
  explicit EF table mappings.
- `resolution_mode`: `strict`, `fuzzy`, or `llm`.
- `candidates_considered`: the candidate node ids ranked for the decision.
- `llm_model`, `llm_rationale`, `chunk_ids`: populated when applicable.

The deterministic `original_edge_key` avoids using the `graph_edges.id`
BIGSERIAL, which changes after invalidation/reprocessing.

Manual trigger:

```bash
curl -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  "https://app.cappyfy.com/api/repositories/$REPO_ID/graph/reconcile" \
  -d '{"commit_sha":"'$COMMIT_SHA'","mode":"all"}'
```

Cost-controlled/offline run:

```bash
curl -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  "https://app.cappyfy.com/api/repositories/$REPO_ID/graph/reconcile" \
  -d '{"commit_sha":"'$COMMIT_SHA'","mode":"no-llm"}'
```

Rollout for `static_roslyn@0.2.0` plus `llm_gap@0.2.0`:

1. Deploy the Roslyn binary in the sandbox.
2. Invalidate rows for the target repository with `source_extractor='static_roslyn'`.
3. Re-materialize the target repository graph.
4. Invalidate stale reconciliation rows with `source_extractor='llm_gap'`.
5. Deploy the `llm_gap` extractor in the API image.
6. Run reconciliation with `mode='strict-only'` first and inspect
   `placeholder_kinds.table_physical`.
7. Optionally run `mode='all'` with a small `limit` before a full LLM run.

Latest run summary:

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "https://app.cappyfy.com/api/repositories/$REPO_ID/graph/reconciliation-summary?commit_sha=$COMMIT_SHA"
```

The summary includes top-level counters and a `placeholder_kinds` breakdown:

```json
{
  "ref_entity": {"total": 1713, "resolved_strict": 238, "resolved_fuzzy": 0, "resolved_llm": 4, "unresolved": 1471},
  "table_physical": {"total": 880, "resolved_strict": 800, "resolved_fuzzy": 0, "resolved_llm": 0, "unresolved": 80}
}
```

To rerun only one extractor slice after bumping its version:

```bash
curl -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  "https://app.cappyfy.com/api/repositories/$REPO_ID/graph/invalidate" \
  -d '{"commit_sha":"'$COMMIT_SHA'","source_extractor":"static_sql"}'

curl -X POST \
  -H "Authorization: Bearer $TOKEN" \
  "https://app.cappyfy.com/api/repositories/$REPO_ID/graph/materialize?commit_sha=$COMMIT_SHA"
```

Use `source_extractor="static_roslyn"` for C# rows, `static_sql` for standalone
SQL rows, `doc_import` for indexed schema documents, and `static_js` for the
original JavaScript/TypeScript extractor.
Use `source_extractor="llm_gap"` to invalidate only reconciliation edges:

```bash
curl -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  "https://app.cappyfy.com/api/repositories/$REPO_ID/graph/invalidate" \
  -d '{"commit_sha":"'$COMMIT_SHA'","source_extractor":"llm_gap"}'
```

## Ad-hoc SQL

```sql
SELECT kind, source_extractor, count(*)
FROM graph_nodes
WHERE repo_id = :repo_id AND commit_sha = :commit_sha
GROUP BY kind, source_extractor
ORDER BY count(*) DESC;

SELECT source_id, type, target_id, target_external
FROM graph_edges
WHERE repo_id = :repo_id
  AND commit_sha = :commit_sha
  AND type IN ('calls', 'queries', 'persists', 'references', 'foreign_key')
LIMIT 100;
```

Unresolved DB placeholders:

```sql
SELECT source_id, target_external, confidence, evidence->>'snippet' AS snippet
FROM graph_edges
WHERE repo_id = :repo_id
  AND commit_sha = :commit_sha
  AND source_extractor = 'static_roslyn'
  AND target_external LIKE 'ref:%';
```

Explicit EF table mappings waiting for reconciliation:

```sql
SELECT source_id, target_external, evidence->'attrs' AS attrs
FROM graph_edges
WHERE repo_id = :repo_id
  AND commit_sha = :commit_sha
  AND source_extractor = 'static_roslyn'
  AND type = 'maps_to_table'
  AND target_external LIKE 'table:%';
```

Standalone SQL entities:

```sql
SELECT kind, name, path, attrs
FROM graph_nodes
WHERE repo_id = :repo_id
  AND commit_sha = :commit_sha
  AND source_extractor = 'static_sql'
ORDER BY kind, name
LIMIT 100;
```

Document-imported schema entities:

```sql
SELECT kind, name, attrs->>'chunk_index' AS chunk_index
FROM graph_nodes
WHERE repo_id = :repo_id
  AND commit_sha = :commit_sha
  AND source_extractor = 'doc_import'
ORDER BY kind, name
LIMIT 100;
```

Resolved Roslyn database references:

```sql
SELECT
  source_id,
  target_id,
  confidence,
  evidence->'attrs'->>'resolution_mode' AS resolution_mode,
  evidence->'attrs'->>'original_target_external' AS original_ref
FROM graph_edges
WHERE repo_id = :repo_id
  AND commit_sha = :commit_sha
  AND source_extractor = 'llm_gap'
  AND type = 'resolves_to';
```

## Known Limits

- No LLM extraction.
- No embeddings or vector columns.
- No PageRank or centrality.
- No gap-filling beyond reconciliation: Phase 2B only links existing `ref:*`
  and `table:*` placeholders to existing schema nodes.
- Exact duplicate sandbox edges are collapsed by the unique index on
  `(repo_id, commit_sha, source_id, target, type)`.
- Roslyn v0 does not emit lambdas, parameters, primitive type edges, property
  getter/setter calls, generic instantiation edges, or cross-language symbol
  resolution from C# names to SQL/schema-doc entities.
- SQL v0 does not emit sequence/domain/type nodes, schema nodes, operational SQL
  nodes, or automatic links from SQL table nodes to `ref:` placeholders emitted
  by other extractors.
- Doc import v0 only supports `markdown_schema_catalog`; it does not emit chunk,
  constraint, index, view, procedure, or embedding nodes.
- LLM reconciliation v0 does not batch calls, does not reconcile cross-repo, and
  does not create new table/column facts.
- Roslyn `maps_to_table` v0 does not infer convention-based mappings and does
  not extract column-level mappings such as `HasColumnName`.
