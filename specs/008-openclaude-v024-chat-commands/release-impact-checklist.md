# Release Impact Validation Checklist

- [X] Every v0.18.0-v0.24.0 release theme from `spec.md` appears in `release-impact-matrix.md`.
- [X] Every new UI decision links to one or more implementation tasks.
- [X] Every existing UI validation decision links to a smoke or regression task.
- [X] Every runtime-only decision links to runtime audit or sandbox validation evidence.
- [X] Every out-of-scope decision includes a product or safety rationale.
- [X] Provider enablement remains outside scope unless an admin/catalog task explicitly adds it.
- [X] Production update/push/deploy remains outside scope for this feature.
- [X] OAuth callback handling does not expose raw callback payloads or tokens.
- [X] Command families include model, context, cost, bughunter, reports, repo map, background sessions, goal/session, update/runtime and doctor diagnostics.
- [X] Command catalog completeness is checked against the v0.24 fallback seed and runtime discovery output.

Observed on 2026-07-21:

```text
Release impact coverage OK: 11 commands and 16 required terms checked.
```
