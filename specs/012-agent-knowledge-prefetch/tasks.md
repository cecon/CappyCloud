# Tasks: Memória e grafo automáticos, com teto de custo

**Input**: [spec.md](spec.md), [plan.md](plan.md)

- [x] T001 Rota `GET /workspaces/:slug/knowledge/query` e `queryGraph` em `services/sandbox/knowledge_handler.js`, com teste
- [x] T002 `services/cappycloud_agent/_knowledge_prefetch.py` (consulta, renderização e injeção), com `services/api/tests/unit/test_knowledge_prefetch.py`
- [x] T003 Chamar a injeção em todo turno em `_task_context.py`, atualizando `test_claude_cli_lean_resume.py`
- [x] T004 `maxTurns` no `query()` do Claude CLI e fim no teto sem erro, com testes do mapper
- [x] T005 Extração de memória no modelo barato, com teste
- [ ] T006 Depois do deploy: comparar o custo médio por pergunta do proteus (SC-003)
