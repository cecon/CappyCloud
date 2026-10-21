# Feature Specification: Memória e grafo consultados automaticamente, com teto de custo

**Feature Branch**: `claude/project-thread-k6yp5g`

**Created**: 2026-10-11

**Status**: Draft

**Input**: O dono do produto viu que o agente quase nunca consulta o graphify e o
agentmemory e que cada pergunta custa caro (proteus, 01/09 a 08/10/2026: 36
perguntas, US$ 18,87 em `messages.cost_usd`, cerca de US$ 0,52 por pergunta).
Pediu que a consulta fique automática.

## Diagnóstico

- Memória e grafo só aparecem como texto no CLAUDE.md do workspace
  (`services/sandbox/workspace_claude_md.js`), ensinando comandos de shell. O
  agente prefere buscar no código com `rg` e raramente roda esses comandos.
- Cada chamada de ferramenta reenvia o contexto inteiro, e o `query()` do Claude
  CLI não tinha teto de passos.
- A extração de memória após cada resposta usava o modelo da conversa, que pode
  ser o Opus.

## Clarifications

### Session 2026-10-11

- Q: A injeção vai no CLAUDE.md? → A: Não. O CLAUDE.md é fixo por workspace e
  vale para todas as conversas. O achado depende da pergunta, então vai no
  prompt do turno, antes da mensagem do usuário.
- Q: Em sessão retomada também? → A: Sim. A pergunta nova traz achados novos. O
  texto é curto para não engordar o histórico.
- Q: Quanto injetar? → A: até 4 memórias de 500 caracteres e um trecho do grafo
  (`--budget 600`, até 2.500 caracteres). Ajustável por
  `KNOWLEDGE_PREFETCH_MEMORIES` e `KNOWLEDGE_PREFETCH_GRAPH_BUDGET`.
- Q: Qual o teto de passos? → A: 40 por pergunta (`CLAUDE_MAX_TURNS`). Ao bater
  no teto, a resposta sai com o que já tem, um aviso e o custo registrado. Não
  vira erro.
- Q: Como controlar o tamanho da janela da conversa? → A: o Claude CLI
  (2.1.281) compacta sozinho quando a janela chega perto do limite, mas o padrão
  "auto" segue a janela do modelo, que pode chegar a 1M de tokens. O sandbox passa
  `CLAUDE_CODE_AUTO_COMPACT_WINDOW=150000` (sobrescrevível pelo ambiente). Não há
  controle para descartar resultados de ferramenta antigos: nessa versão a gestão
  de contexto pela API (`USE_API_CONTEXT_MANAGEMENT`) está desligada no código.
  O cache de prompt já é de 1 hora na assinatura (padrão automático do CLI).
- Q: Qual modelo extrai memória? → A: Haiku (`MEMORY_EXTRACT_MODEL`), seja qual
  for o modelo da conversa.

## Requirements

- **FR-001**: A cada turno de conversa de workspace, a API consulta a memória do
  workspace e o grafo com a pergunta do usuário e injeta os achados antes da
  mensagem.
- **FR-002**: Sem achados, sem workspace, sem URL do sandbox, com falha ou com
  demora (8 s), o prompt segue inalterado e o turno não é bloqueado.
- **FR-003**: O sandbox expõe `GET /workspaces/:slug/knowledge/query?q=&budget=`.
  Ele roda `graphify query` no grafo do workspace e devolve texto vazio quando
  não há grafo.
- **FR-004**: O Claude CLI roda com `maxTurns` (padrão 40). Parar no teto é um
  fim normal, com aviso ao usuário.
- **FR-005**: A extração de memória usa o modelo barato, não o da conversa.
- **FR-006**: O Claude CLI compacta a conversa ao chegar perto de 150 mil tokens
  (`CLAUDE_CODE_AUTO_COMPACT_WINDOW`), em vez da janela cheia do modelo.

## Success Criteria

- **SC-001**: Em conversas de workspace com memória gravada, o prompt de toda
  pergunta traz a seção "Conhecimento do workspace".
- **SC-002**: Nenhuma pergunta passa de 40 passos do agente.
- **SC-003**: O custo médio por pergunta do proteus cai em relação aos US$ 0,52
  da base (medir 2 semanas depois do deploy, pelo relatório de uso).

## Fora desta entrega

- Roteamento de perguntas simples para o Haiku e modelo próprio para subagentes.
- Índice de símbolos ADVPL/TLPP (o graphify não lê essas linguagens).
- Gravar por mensagem a quebra de cache (thread "Separar leitura e gravação de
  cache no custo").
