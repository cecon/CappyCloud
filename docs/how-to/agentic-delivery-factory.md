# Agentic Delivery Factory

Spec Kit:

- `specs/001-agentic-delivery-factory/plan.md`
- `specs/001-agentic-delivery-factory/data-model.md`
- `specs/001-agentic-delivery-factory/quickstart.md`

## Security Invariants

- Knowledge retrieval is filtered by authorized repository/domain before ranking or UI exposure.
- Ordinary repository visibility does not authorize external actions.
- External actions require an active `authorize_external_action` agentic delivery permission and completed gates at execution time.
- Sensitive surface management requires platform admin rights or `manage_sensitive_surfaces`.
- Generated changes remain review-only until external action authorization succeeds.

## Local Validation

```bash
cd services/api
D:\projetos\CappyCloud\services\api\.venv\Scripts\python.exe -m ruff check .
D:\projetos\CappyCloud\services\api\.venv\Scripts\python.exe -m ruff format --check .
D:\projetos\CappyCloud\services\api\.venv\Scripts\python.exe -m mypy app/
D:\projetos\CappyCloud\services\api\.venv\Scripts\python.exe -m pytest
```

```bash
pnpm --dir web exec tsc --noEmit
```

Last local result:

- API `ruff check .`: passed.
- API `ruff format --check .`: passed.
- API `mypy app/`: passed.
- API `pytest`: 567 passed, coverage 80.01%.
- Web `pnpm --dir web exec tsc --noEmit`: passed.
- Web `pnpm --dir web lint`: blocked locally because `@eslint/js` is not installed/resolvable from `web/eslint.config.js`.
- Web `pnpm --dir web build`: blocked locally because the TypeScript build cannot resolve `vite/client`.

## Demo Script

1. Open `/agentic-delivery`.
2. Select an authorized repository and domain.
3. Create and prepare a cycle.
4. Start execution; the task is created in review-only mode.
5. Load review and approve gates.
6. Search reusable knowledge and confirm only authorized repository/domain items appear.
7. Configure a sensitive surface for fiscal/electronic-document keywords.
8. Attempt external authorization only after the cycle is approved and the acting user has the feature permission.

## Current Implementation Notes

- The first implementation slice includes domain rules, persistence schema, ports, SQLAlchemy adapter, use cases, HTTP handlers, typed frontend API, and the operational page.
- Agent prompt/context enrichment for review-only cycles is implemented for the MVP path.
- Exhaustive SQLAlchemy adapter and performance coverage remain in later tasks in `tasks.md`.
