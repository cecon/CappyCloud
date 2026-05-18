# ADR-003 — Ferramentas Semânticas LSP/AST Sob Demanda

**Status:** Aceite
**Data:** 2026-05-16
**Contexto:** CappyCloud — precisão e custo de agentes em código grande

---

## Contexto

O agente openclaude roda headless no sandbox. Ele consegue investigar código com
`rg`, leitura de arquivos, comandos de build/teste/lint e MCPs configurados, mas
essa abordagem pode gastar muitos tokens e ser frágil em refactors estruturais.

Language servers e ferramentas AST ajudam em navegação semântica, diagnósticos,
referências, tipos e transformações estruturais. Ao mesmo tempo, manter LSPs
residentes por sessão aumenta uso de CPU/memória e tempo de inicialização.

---

## Decisão

Instalar ferramentas semânticas no sandbox como binários e bibliotecas
disponíveis no `PATH`, mas usá-las sob demanda. Nenhum language server fica
residente por padrão.

Ferramentas incluídas:

- TypeScript/JavaScript: `typescript-language-server`, `tsc`, `tsserver`,
  `ts-morph`;
- Python: `pyright`, `basedpyright`, `ruff`, `libcst`;
- Multi-linguagem/AST: `ast-grep`, `tree-sitter`.

Essas ferramentas podem ser usadas diretamente por comandos, por scripts
temporários do agente ou por MCPs configurados pelo usuário.

---

## Regras derivadas

1. Use `rg` para localização inicial simples.
2. Use LSP/typecheck quando a tarefa envolver símbolos, tipos, definições,
   referências ou imports.
3. Use AST quando a tarefa envolver refactor estrutural, renames, chamadas,
   imports ou edições repetitivas.
4. Não mantenha language server persistente sem necessidade clara.
5. Prefira ferramentas do projeto quando existirem (`pnpm lint`, `pytest`,
   `ruff`, `mypy`, `tsc`, etc.).
6. Valide mudanças com lint/typecheck/testes adequados antes de PR.

---

## Consequências

### Positivas

- Reduz leitura redundante de arquivos e consumo de tokens em investigações
  grandes.
- Aumenta precisão em refactors e diagnósticos de tipo.
- Mantém baixo custo em sessões simples, porque servidores não ficam sempre
  ativos.
- Prepara o runtime para MCPs de LSP sem novo rebuild da imagem.

### Negativas / Trade-offs

- A imagem do sandbox fica maior.
- O primeiro uso de algumas ferramentas ainda pode ter custo de indexação.
- O agente precisa escolher quando vale a pena usar LSP/AST em vez de busca
  textual.

---

## Alternativas consideradas

### Não instalar ferramentas semânticas

Rejeitado. Mantém a imagem menor, mas força o agente a depender de busca textual
e validações tardias, piorando precisão em projetos grandes.

### Rodar LSP persistente por sessão

Rejeitado como padrão inicial. Melhora latência de chamadas semânticas depois do
primeiro index, mas consome memória/CPU mesmo em conversas que não precisam
desse nível de análise.

### Extensão VS Code como fonte semântica

Rejeitado para o runtime headless. Extensão de editor melhora UX humana, mas não
resolve o agente rodando dentro do sandbox via gRPC.

---

## Referências

- `services/sandbox/Dockerfile`
- `services/sandbox/CLAUDE.md`
- `docs/decisions/adr-002-sandbox-runtime-and-worktree-sessions.md`
