# Feature Specification: OpenClaude v0.17.1 UI Debt Audit

**Feature Branch**: `[004-openclaude-v017-ui-debt]`

**Created**: 2026-06-18

**Status**: Draft

**Input**: User description: "Atualizar o OpenClaude para v0.17.1 e avaliar as dividas tecnicas de UI para atender as novas features das releases v0.16.0, v0.16.1, v0.17.0 e v0.17.1."

## Clarifications

### Session 2026-06-19

- Q: Como o CappyCloud deve tratar o cache e a persistencia de sessao novos do OpenClaude?→ A: Desabilitar ou restringir para uso interno de execucao; UI e historico sempre vem do CappyCloud.
- Q: Como o CappyCloud deve tratar fallback automatico por rate limit?→ A: Permitir fallback automatico somente para modelos autorizados no catalogo do CappyCloud, com indicacao sanitizada do modelo final usado.
- Q: Como `MCP_SKILLS` e `skill://` devem entrar nesta atualizacao?→ A: Permitir `skill://` apenas como fonte visivel/auditavel, sem substituir skills de repo nem ativar sem cadastro/autorizacao do CappyCloud.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Mapear impacto visual do salto para v0.17.1 (Priority: P1)

Como pessoa responsavel pela atualizacao do runtime, quero uma matriz completa de impacto UI para cada item de release entre v0.16.0 e v0.17.1, para planejar a atualizacao sem esconder dividas tecnicas ou criar telas sem necessidade.

**Why this priority**: O runtime atual do sandbox ainda esta fixado na revisao da v0.15.0. O salto ate v0.17.1 inclui cache/sessao, providers, catalogo de modelos, seguranca, mensagens de tools e estados de busca. A equipe precisa separar o que e runtime puro, o que exige validacao de UI existente e o que vira divida nova de UI.

**Independent Test**: Pode ser testado revisando a matriz de escopo contra as releases v0.16.0, v0.16.1, v0.17.0 e v0.17.1 e confirmando que 100% dos itens possuem decisao de impacto.

**Acceptance Scenarios**:

1. **Given** as notas oficiais das releases v0.16.0, v0.16.1, v0.17.0 e v0.17.1, **When** a avaliacao for concluida, **Then** cada item possui decisao: nova divida UI, validar UI existente, somente runtime/operacao, ou fora de escopo do CappyCloud.
2. **Given** um item classificado como sem nova UI, **When** a equipe revisar a spec, **Then** a justificativa explica qual comportamento existente cobre o item ou por que ele nao pertence a superficie visual do CappyCloud.
3. **Given** um item classificado como nova divida UI, **When** a equipe iniciar o planejamento, **Then** a divida descreve o resultado esperado para o usuario sem impor implementacao tecnica.

---

### User Story 2 - Preservar continuidade de conversa e sessao (Priority: P2)

Como pessoa usando o chat do CappyCloud, quero que historico, retomada de sessao, modo de permissao, progresso e mensagens continuem coerentes apos o runtime ganhar cache e persistencia propria, para nao receber resposta em contexto errado nem ver estado visual obsoleto.

**Why this priority**: A v0.17.0 adiciona cache de conversa e persistencia de sessao no OpenClaude. O CappyCloud ja possui conversa persistida, estado de sessao e modo de permissao por conversa. Sem uma decisao de produto, dois donos de estado podem gerar mensagens duplicadas, permissao errada, retomada confusa ou custo associado ao turno errado.

**Independent Test**: Pode ser testado alternando entre duas conversas, recarregando a pagina, retomando sessao e enviando nova mensagem; a UI deve mostrar exatamente a conversa ativa, o modo de permissao correto, o progresso correto e o historico esperado.

**Acceptance Scenarios**:

1. **Given** duas conversas abertas no mesmo sandbox, **When** o usuario alterna entre elas e retoma uma sessao, **Then** a UI mostra apenas mensagens, progresso e modo de permissao da conversa ativa.
2. **Given** uma conversa reaberta apos recarregar a pagina, **When** o runtime possui cache ou sessao propria, **Then** esse estado fica restrito a execucao interna e a UI usa somente historico, permissao e metadados autorizados pelo CappyCloud.
3. **Given** o runtime encerra ou perde a sessao, **When** a UI recebe erro ou retomada parcial, **Then** o usuario ve estado acionavel e nao um historico aparentemente sincronizado mas incorreto.

---

### User Story 3 - Tornar fallback de provider e catalogo de modelos confiaveis (Priority: P3)

Como pessoa usando ou demonstrando o chat, quero saber qual modelo foi escolhido, quando houve fallback por limite de uso e como isso afeta custo/capacidade, para confiar no resultado e na cobranca exibida.

**Why this priority**: A v0.17.0 adiciona fallback automatico por rate limit, novos modelos, descoberta dinamica NVIDIA, ajustes OpenGateway, correcao de prioridade Mistral e aposentadoria de modelos Xiaomi. O CappyCloud tem catalogo autorizado, modelo escolhido na UI e custo real por provider; a UI nao pode sugerir que um modelo foi usado quando o runtime trocou silenciosamente.

**Independent Test**: Pode ser testado simulando um fallback de provider ou indisponibilidade de modelo; a conversa deve mostrar modelo/custo final coerentes e uma indicacao sanitizada quando o runtime confirmar substituicao.

**Acceptance Scenarios**:

1. **Given** o usuario seleciona um modelo autorizado, **When** o runtime executa sem fallback, **Then** a UI mantem modelo, custo e capacidades consistentes com a selecao.
2. **Given** o provider aplica fallback por limite de uso, **When** existe alternativa autorizada no catalogo do CappyCloud e o turno termina, **Then** a UI mostra uma indicacao sanitizada de fallback e o modelo final usado, sem expor chaves, prompts ocultos ou logs brutos.
3. **Given** um modelo foi removido ou aposentado no catalogo, **When** o usuario abre uma conversa antiga, **Then** a UI mostra que a selecao anterior nao esta mais disponivel e oferece uma alternativa autorizada.

### Edge Cases

- O trabalho da v0.15.0 pode ainda nao estar mergeado; a v0.17.1 depende de reconciliar a base de permissao por sessao antes de alterar o runtime.
- O GitHub mostra que v0.18.0 ja existe em 2026-06-10; esta especificacao mantem v0.17.1 como alvo explicito e nao inclui features de v0.18.0.
- Cache de conversa do runtime pode conter estado diferente do banco do CappyCloud; esse cache deve ser desabilitado ou restringido a uso interno de execucao, e a UI deve usar sempre o estado autorizado do CappyCloud.
- Retomada de sessao pode ocorrer em conversa com modo de permissao alterado desde o ultimo turno; o modo visivel e persistido da conversa deve governar novas execucoes.
- Fallback de provider pode trocar modelo, capacidade de visao, contexto ou preco; fallback automatico so pode usar modelo autorizado no catalogo do CappyCloud, e a UI nao deve calcular custo por estimativa local quando provider retornar uso real.
- Novos modelos upstream podem nao estar autorizados para o usuario ou ambiente; a UI deve manter o catalogo permitido do CappyCloud.
- Skills descobertas por MCP podem nao vir dos arquivos versionados do repositorio; a UI/admin deve diferenciar a origem, e `skill://` nao pode substituir skills de repo nem ser ativado sem cadastro e autorizacao do CappyCloud.
- Saida de tool com erro pode conter paths, comandos ou mensagens sensiveis; a UI deve exibir informacao util e sanitizada.
- Busca de conversas pode estar filtrada quando a lista e atualizada por reload/cache; contadores, pagina incremental e estado vazio devem continuar coerentes.

## Requirements *(mandatory)*

### Release Item UI Scope

| Release item | CappyCloud UI decision | Reason |
|---|---|---|
| v0.16.0 local-model doctor warning | Validar UI existente | O CappyCloud usa modelo dinamico por conversa e OpenRouter como caminho principal; se local model estiver habilitado, aviso deve aparecer como diagnostico operacional sanitizado, nao como nova tela de chat. |
| v0.16.0 MCP_SKILLS via `skill://` | Nova divida UI/admin restrita | `skill://` pode aparecer apenas como origem visivel e auditavel. Nao deve substituir skills de repo nem ser ativado sem cadastro e autorizacao do CappyCloud. |
| v0.16.0 suporte OpenCode Zen/Go | Somente runtime/catalogo | Nao vira UI enquanto o provider nao estiver no catalogo autorizado do CappyCloud. |
| v0.16.0 `process.title` openclaude | Somente runtime/operacao | Ajuda observabilidade de processo, sem impacto visual direto. |
| v0.16.0 agent model overrides | Validar UI existente | O CappyCloud ja tem modelo por conversa e agentes por repositorio; precisa garantir que override nao torne modelo/custo exibidos inconsistentes. |
| v0.16.0 autocompact retry | Validar UI existente | Afeta continuidade; a UI deve manter stream, progresso e erro final coerentes. |
| v0.16.0 saida de comando bash `!` | Validar UI existente | Saida de comandos deve continuar visivel em tool activity ou erro sanitizado. |
| v0.16.0 comando terminal `/dream` | Fora de escopo do CappyCloud | Comando interativo do OpenClaude nao deve virar UI se nao houver fluxo headless equivalente. |
| v0.16.0 ajustes de CI/release/docs | Somente operacao | Nao altera superficie do usuario. |
| v0.16.0 forked-worker messages | Validar UI existente | Se mensagens de subexecucao chegarem pelo stream, a timeline nao deve perder, duplicar ou rotular errado. |
| v0.16.0 largura de simbolos no terminal | Validar UI existente | Mensagens com simbolos devem continuar sem quebra visual ou sobreposicao no chat. |
| v0.16.0 launcher Node e sandbox guard | Somente runtime/sandbox | Deve ser validado no build e no erro de startup, nao como novo componente. |
| v0.16.0 leitura de markdown em lote e limite de tamanho | Validar UI existente | Melhora startup; a UI deve manter estados de carregamento e erro quando skills/docs sao grandes. |
| v0.16.0 limites Ollama e remote Ollama | Somente runtime/catalogo | Nao ha nova UI enquanto provider local/remoto nao for habilitado no ambiente. |
| v0.16.0 OpenGateway exige chave no cadastro | Validar admin existente | Se cadastro de provider estiver exposto, erro deve ser claro e sem vazar chave. |
| v0.16.0 guard de falha de tool | Validar UI existente | Falhas de tool nao devem desaparecer apos eventos de sucesso posteriores. |
| v0.16.0 prompt de permissao com input presente | Validar UI existente | `ActionRequired` deve continuar visivel sem conflitar com rascunho/input do usuario. |
| v0.16.0 progresso cumulativo de teammate | Validar UI existente | Contadores de tokens, tools e progresso nao devem resetar entre prompts da mesma execucao. |
| v0.16.0 thinking/refusal/provider compat | Validar UI existente | Estados de pensamento, recusa e metricas de provider devem ser exibidos sem falsos positivos ou custo incorreto. |
| v0.16.1 release workflow | Somente operacao | Corrige pipeline de release upstream, sem impacto visual do produto. |
| v0.17.0 cache de conversa e persistencia de sessao | Nova divida UI/UX | Precisa decidir como convive com historico, SessionStore, modo de permissao e retomada ja controlados pelo CappyCloud. |
| v0.17.0 otimizacao de memoria multi-sessao | Validar UI existente | Deve reduzir instabilidade; a UI precisa validar muitas sessoes abertas sem progresso preso ou lista obsoleta. |
| v0.17.0 MiniMax M3 com contexto grande | Validar catalogo/model picker | Novo modelo so aparece se autorizado; contexto, custo e capacidades precisam ser coerentes. |
| v0.17.0 descoberta dinamica NVIDIA NIM | Nova divida admin/catalogo se habilitado | Descoberta dinamica exige status de sync e autorizacao antes de aparecer para usuarios. |
| v0.17.0 OpenGateway MiniMax/Qwen/Gemini ids | Validar catalogo/model picker | IDs novos ou alterados nao podem quebrar conversas antigas nem selecionar modelo nao autorizado. |
| v0.17.0 fallback automatico por rate limit | Nova divida UI/UX | Quando runtime trocar provider/modelo, a conversa deve mostrar indicacao sanitizada e custo/modelo final correto. |
| v0.17.0 patrocinador/tip | Fora de escopo do CappyCloud | Mensagem promocional upstream nao deve aparecer na UI do produto. |
| v0.17.0 aposentadoria Xiaomi MiMo | Validar catalogo/model picker | Modelos removidos devem aparecer como indisponiveis ou migrados, sem fallback silencioso. |
| v0.17.0 heuristica de `reasoning_content` | Validar UI existente | A UI nao deve renderizar pensamento/diagnostico falso como conteudo principal. |
| v0.17.0 BashTool com output em erro | Validar UI existente | Erro de tool deve incluir contexto util, truncado e sanitizado. |
| v0.17.0 limite de prompt cron duravel | Somente runtime/automacao | Sem nova UI enquanto cron duravel nao for exposto como feature do CappyCloud. |
| v0.17.0 merge de hooks/plugins marketplace | Validar admin se plugins estiverem habilitados | Configuracoes vindas de suplemento nao devem sobrescrever settings visiveis sem aviso. |
| v0.17.0 raw mode e promptinput bash mirror | Fora de escopo direto | Corrige UI terminal do OpenClaude; validar apenas se aparecer comportamento equivalente no chat. |
| v0.17.0 seguranca contra CRLF/path injection/leak | Nova divida de hardening UI | Mensagens de erro, paths e outputs devem continuar sanitizados em chat, diagnosticos e admin. |
| v0.17.0 modelos Mistral e prioridade | Validar catalogo/model picker | Picker deve mostrar modelos autorizados e manter prioridade definida pelo CappyCloud. |
| v0.17.0 erro especifico de visao quando provider retorna 404 | Validar UI existente | Envio de imagem deve gerar erro acionavel sobre capacidade/indisponibilidade do modelo. |
| v0.17.0 typechecks de cache/hook/appstate/imports/add-dir | Validar regressao UI | Itens sao internos, mas cobrem estados de historico, hooks e adicionamento de diretorios que podem afetar estabilidade visual. |
| v0.17.0 default Mistral vibe cli | Validar catalogo/model picker | Default upstream nao deve sobrepor default autorizado do ambiente. |
| v0.17.0 respostas de permissao VS Code | Fora de escopo do CappyCloud | Integra fluxo VS Code upstream, nao o chat web. |
| v0.17.1 typecheck do setup GitHub app | Validar admin se fluxo existir | Se houver configuracao GitHub app no CappyCloud, estado do wizard deve ser testado; caso contrario fica fora de escopo visual. |
| v0.17.1 typecheck do estado de busca | Validar UI existente | O CappyCloud possui busca de conversas; filtro, contador, limpar busca e paginacao incremental precisam de regressao visual/funcional. |

### Functional Requirements

- **FR-001**: System MUST update the agent runtime target to OpenClaude v0.17.1 and keep the selected upstream revision traceable.
- **FR-002**: System MUST classify every release item from v0.16.0, v0.16.1, v0.17.0 and v0.17.1 as new UI debt, validation of existing UI, runtime/operation only, or outside CappyCloud scope.
- **FR-003**: System MUST preserve the CappyCloud conversation as the visible source of truth for messages, selected repository, selected model, permission mode, usage and cost.
- **FR-004**: System MUST disable or constrain OpenClaude conversation cache/session persistence so it is only an internal execution detail and never the source of truth for visible history, permission mode, selected repository, selected model, usage or cost.
- **FR-005**: Users MUST be able to distinguish initial startup, session resume, runtime retry and final failure states without duplicated progress or stale conversation data.
- **FR-006**: System MUST preserve per-session permission behavior introduced for v0.15.0 when the runtime is upgraded to v0.17.1.
- **FR-007**: System MUST keep model visibility and selection governed by the CappyCloud authorized model catalog, not by upstream provider catalogs alone.
- **FR-008**: System MUST allow automatic provider/model fallback only when the final model is authorized in the CappyCloud catalog and MUST show a sanitized fallback indicator when the final model differs from the user-selected model.
- **FR-009**: System MUST keep usage and cost displays tied to provider-returned usage and current catalog pricing for the final authorized model used; if no authorized fallback exists, the user must receive an actionable error instead of a silent substitution.
- **FR-010**: System MUST treat `skill://` as an auditable runtime skill source only when registered and authorized by CappyCloud; it MUST NOT replace repository skills or become active solely because OpenClaude discovers it at runtime.
- **FR-011**: System MUST ensure tool errors, provider refusals, path-related errors and startup diagnostics are useful to the user without exposing secrets, hidden prompts, raw logs or repository contents.
- **FR-012**: System MUST validate existing chat states for normal answer, resumed session, tool start/result/error, action required, payload diagnostics, model label, usage, cost, cancellation, permission warning and stream error.
- **FR-013**: System MUST validate existing model picker states for unavailable model, retired model, vision-only mismatch, provider error, no authorized models and large-context model metadata.
- **FR-014**: System MUST validate existing conversation search states for filtered list, empty result, clear action, lazy loading count and conversation switch while filtered.
- **FR-015**: System MUST document which local OpenClaude patches are retained, changed, removed or made obsolete by v0.17.1 before implementation is marked ready.

### Key Entities *(include if feature involves data)*

- **Release Delta Item**: One upstream change between OpenClaude v0.16.0 and v0.17.1, with version, category, source evidence and CappyCloud UI decision.
- **UI Debt Item**: Product-visible gap that must be resolved before the runtime update is safe to demonstrate or release.
- **Runtime Session State**: User-visible state of a conversation execution, including initial startup, resumed session, retry, active stream, action required and terminal status. OpenClaude cache/session state may support execution internally but must not define the visible conversation history.
- **Provider Fallback Notice**: Sanitized user-facing indication that the runtime changed provider or model after a rate limit or provider failure, limited to final models authorized by the CappyCloud catalog.
- **Model Catalog Entry**: Authorized model visible in CappyCloud, with provider, capabilities, context window, status, pricing and default eligibility.
- **Runtime Skill Source**: Origin of a skill available to the agent, such as repository-versioned file, sandbox/global registration or registered `skill://` MCP resource. Runtime-discovered sources are visible for audit only until CappyCloud authorizes them.
- **Agent Runtime Pin**: Traceable OpenClaude version and upstream commit selected for the sandbox build.

### Runtime Context, Security & Evidence *(mandatory when applicable)*

- **RC-001**: External release evidence reviewed: GitHub releases `v0.16.0`, `v0.16.1`, `v0.17.0` and `v0.17.1` from `https://github.com/Gitlawb/openclaude/releases`. The `v0.17.1` release page lists 2026-06-05 and commit `1b7e550`; tag lookup on 2026-06-18 returned `refs/tags/v0.17.1` at `1b7e55058cca57f2f83d7e229441631794286c1a`.
- **RC-002**: External release evidence also shows `v0.18.0` released on 2026-06-10 at `b0064575a741ddd851a84812372d8d4b515cd0a2`; this is explicitly out of scope for the v0.17.1 update.
- **RC-003**: Repository evidence reviewed: `services/sandbox/Dockerfile:98` currently pins OpenClaude to `670744fc70353f2270e86531dffa1c06f4fac79c` from the v0.15.0 work; `docs/ARCHITECTURE.md:82` describes OpenClaude inside the sandbox via gRPC; `docs/ARCHITECTURE.md:112` documents the per-conversation permission mode contract.
- **RC-004**: Repository evidence reviewed: `docs/how-to/agent-runtime-context.md:55` defines session permission behavior and `docs/how-to/agent-runtime-context.md:91` requires dynamic model and real provider cost behavior.
- **RC-005**: Repository evidence reviewed: `web/src/pages/ChatPage.tsx:99` defines permission-mode labels; `web/src/pages/ChatPage.tsx:507` holds conversation search and chat runtime state; `web/src/pages/ChatPage.tsx:1524` renders conversation search; `web/src/api.ts:765` sends stream requests with optional model, attachments and permission mode.
- **RC-006**: Security behavior is product-visible for provider fallback, tool errors, path errors, runtime diagnostics, skills and repository context. UI messages must be sanitized and must not expose provider keys, hidden prompts, raw logs, repository file contents or tool input bodies.
- **RC-007**: Sandbox image build and local patch audit are in scope. Production deployment, image push, Portainer/Swarm rollout and automatic container replacement are out of scope unless a later plan adds them explicitly.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of release items from v0.16.0 through v0.17.1 have a documented CappyCloud UI decision before implementation planning starts.
- **SC-002**: 100% of new UI debt items are mapped to an independently testable user-facing outcome before tasks are generated.
- **SC-003**: In session resume tests, users see the correct active conversation, permission mode and latest message state in 100% of tested conversation switches and reloads.
- **SC-004**: When an authorized provider/model fallback is confirmed by runtime metadata, users can identify that fallback and the final model used in under 10 seconds from the completed turn.
- **SC-005**: Existing chat states for normal answer, resumed session, tool activity, tool error, action-required prompt, payload diagnostics, model label, usage, cost, cancellation, permission warning and stream error each have at least one validation scenario before completion.
- **SC-006**: Existing model picker states for unavailable model, retired model, vision mismatch, provider error, no authorized models and large-context model metadata each have at least one validation scenario before completion.
- **SC-007**: Existing conversation search states for filtered list, empty result, clear action, lazy loading count and conversation switch while filtered each have at least one validation scenario before completion.
- **SC-008**: No UI warning, provider fallback notice, tool error or diagnostic introduced by this update displays raw secrets, provider API keys, hidden prompts, repository file contents, raw container logs or unsanitized tool input.
- **SC-009**: The selected OpenClaude runtime revision is traceable to the v0.17.1 tag in 100% of build and review artifacts.

## Implementation Evidence

### Session 2026-07-08

- Runtime pin updated to OpenClaude v0.17.1 tag SHA
  `1b7e55058cca57f2f83d7e229441631794286c1a`.
- Remote tag verification returned `refs/tags/v0.17.1` at
  `1b7e55058cca57f2f83d7e229441631794286c1a`; `refs/tags/v0.18.0` remains
  known and out of scope at `b0064575a741ddd851a84812372d8d4b515cd0a2`.
- Dockerfile patch sequence applies cleanly against v0.17.1 after rebasing
  `multimodal-proto.patch` and `multimodal-grpc-handler.patch`.
- Sandbox image build passed with local tag
  `cappycloud-sandbox-openclaude-v0171-check:latest`.
- Focused runtime tests passed:
  `pytest -o addopts='' services/api/tests/unit/test_agent_runtime_regressions.py services/api/tests/unit/test_agent_permission_mode.py`
  with 19 passed.
- US3 implementation added sanitized fallback metadata, authorized final-model
  enforcement, final-model cost persistence coverage, and a compact chat UI
  notice for runtime fallback.
- Final gates that passed locally: `ruff check .`, `ruff format --check .`,
  `pnpm --dir web lint`, `pnpm --dir web build`, and the Docker sandbox build
  from the pinned v0.17.1 SHA.
- `mypy app/` and full `pytest` remain blocked in this local environment
  because the available Python is 3.12.13 while `services/api/pyproject.toml`
  requires Python `>=3.14` and formats code with `target-version = "py314"`.

## Assumptions

- The requested target is OpenClaude v0.17.1, not the newer v0.18.0 release visible on GitHub.
- The v0.15.0 permission-mode work remains the baseline for this update; if it is not merged, the v0.17.1 plan must reconcile those changes first.
- The CappyCloud chat remains the primary user-facing agent surface. OpenClaude terminal-only features do not automatically become CappyCloud UI requirements.
- The CappyCloud model catalog and authorization rules remain authoritative for what users can select.
- OpenClaude cache/session persistence is not a product-visible history source; visible history, permission mode, selected repository, selected model, usage and cost remain owned by CappyCloud.
- Provider fallback UI is required only when the runtime can report sanitized confirmation that the final provider or model changed, and automatic fallback is allowed only to models authorized in the CappyCloud catalog.
- MCP-discovered skills are considered audit-visible only until the environment registers and authorizes them through CappyCloud; they must not override repository skills.
- Production rollout is separate from this specification.
