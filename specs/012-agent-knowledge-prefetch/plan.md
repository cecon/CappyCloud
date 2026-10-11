# Implementation Plan: Memória e grafo automáticos, com teto de custo

**Spec**: [spec.md](spec.md)

## Abordagem

1. `services/cappycloud_agent/_knowledge_prefetch.py`
   - Usa o slug da sessão de workspace (`workspace_root_of`).
   - Consulta em paralelo `GET /memory/search` e `GET /workspaces/:slug/knowledge/query` no `session_server` do sandbox.
   - Renderiza uma seção curta e a injeta com `inject_section_before_user_message`.
2. `_task_context.prepare_turn_prompt`
   - Chama a injeção em todo turno, inclusive no turno retomado.
   - No openclaude, as linhas `/add` continuam abrindo o prompt.
3. `services/sandbox/knowledge_handler.js`: `queryGraph` (orçamento entre 100 e 2.000 tokens, timeout de 10 s) e a rota `/query`.
4. `services/sandbox/claude_runtime_mapper.js`
   - `maxTurnsPerQuestion()`, a partir de `CLAUDE_MAX_TURNS` (padrão 40).
   - `error_max_turns` vira texto, aviso e `done` com custo.
5. `services/sandbox/memory_extract.js`: `extractionModel()`, a partir de `MEMORY_EXTRACT_MODEL` (padrão `haiku`).

## Constituição

- Sem port nova. A integração com o sandbox vive no pacote do agente (`services/cappycloud_agent`), como a coleta de evidências que já existe. A API (`services/api/app`) não muda.
- Arquivos abaixo de 300 linhas.
- Falha externa nunca bloqueia o turno.
- Modelo do agente segue dinâmico: só a extração de memória fixa o modelo barato, por variável de ambiente.

## Testes

- `services/api/tests/unit/test_knowledge_prefetch.py`: limites, injeção, sessão retomada, falhas e casos sem consulta.
- `services/api/tests/unit/test_claude_cli_lean_resume.py`: a injeção ocorre nos dois tipos de turno.
- `services/sandbox/tests/*.test.js` (`node --test`):
  - `queryGraph`;
  - teto de passos e fim no teto;
  - modelo da extração.
