# Feature Specification: OpenClaude Current Upgrade UI Readiness

**Feature Branch**: `[008-openclaude-current-upgrade]`

**Created**: 2026-08-06

**Status**: Draft

**Input**: User description: "vamos atuar na atulizaçao do openclaude para a versao atual, mas precisamos ver o que teria que adaptar em ui interface para atender"

## Clarifications

### Session 2026-08-06

- Q: Como a UI deve expor token/contexto em tempo real durante a execução? -> A: Expor indicador discreto durante execução, como "contexto usado" ou "processando contexto", sem valor financeiro.
- Q: Como a UI deve apresentar subagents ou sessoes auxiliares do OpenClaude? -> A: Mostrar subagents como atividade agrupada/colapsavel dentro do turno principal.
- Q: Quem deve ver onboarding/OAuth de provider e estados de autenticacao? -> A: Apenas administradores veem onboarding/OAuth de provider e estados de autenticacao.
- Q: O alvo do upgrade deve permanecer movel ate a implementacao ou congelar em uma versao? -> A: Congelar esta feature em OpenClaude 0.27.0; versoes posteriores exigem nova decisao.
- Q: O deploy em producao entra no escopo desta feature? -> A: Nao incluir deploy; entregar runbook de rollout/rollback para execucao posterior, apos teste local.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Mapear Impacto De Interface Do Upgrade (Priority: P1)

Como pessoa responsavel pelo CappyCloud, quero entender quais mudancas das releases atuais do OpenClaude afetam a interface do produto, para atualizar o runtime sem quebrar a experiencia de chat, administracao, catalogo ou demonstracao.

**Why this priority**: O ambiente de producao ja esta em OpenClaude 0.24.0 e a versao publicada atual e 0.27.0. Antes de trocar o runtime, a equipe precisa separar o que exige adaptacao visual, o que exige apenas validacao de estados existentes e o que nao pertence a superficie web do CappyCloud.

**Independent Test**: Pode ser testado revisando uma matriz de impacto para as releases 0.25.0, 0.26.0 e 0.27.0 e confirmando que todos os itens relevantes possuem decisao de UI: adaptar, validar existente, runtime/operacao apenas ou fora de escopo.

**Acceptance Scenarios**:

1. **Given** as notas das releases 0.25.0, 0.26.0 e 0.27.0, **When** a avaliacao for concluida, **Then** cada tema relevante tem uma decisao de impacto para a interface do CappyCloud.
2. **Given** uma mudanca classificada como "adaptar UI", **When** a equipe seguir para planejamento, **Then** a spec descreve o resultado esperado para o usuario sem depender de detalhe de implementacao.
3. **Given** uma mudanca terminal-only do OpenClaude, **When** ela for avaliada, **Then** a spec deixa claro se ela fica fora da UI web ou se precisa aparecer como estado equivalente no chat.

---

### User Story 2 - Preservar O Chat Como Fonte Visual De Verdade (Priority: P1)

Como usuario do CappyCloud, quero que conversas, atividades de tools, subexecucoes, erros, progresso, permissao e custo continuem coerentes apos o upgrade, para confiar no que estou vendo durante turnos curtos e longos.

**Why this priority**: As releases novas trazem feedback de streaming, contagem de tokens, subagents, maior controle de compactacao, ferramentas longas e guardas de falha. Esses itens podem melhorar a experiencia, mas tambem podem gerar duplicidade, estados presos, rotulos incorretos ou custo inconsistente se a UI nao preservar o contrato do CappyCloud.

**Independent Test**: Pode ser testado executando conversas com resposta normal, tool longa, tool com erro, subexecucao, troca de conversa durante streaming e retomada de sessao; a UI deve manter uma linha do tempo clara e sem estado obsoleto.

**Acceptance Scenarios**:

1. **Given** uma tool longa em andamento, **When** o runtime continuar emitindo progresso, **Then** o usuario ve atividade viva e nao recebe erro prematuro de inatividade.
2. **Given** uma tool falha ou o runtime reporta uma permissao expirada, **When** o evento aparece no chat, **Then** a UI mostra uma mensagem acionavel e sanitizada sem perder o resultado final do turno.
3. **Given** um agente dispara subexecucoes a partir de uma sessao multi-repositorio, **When** essas atividades forem visiveis ao CappyCloud, **Then** a conversa mostra subagents como atividade agrupada e colapsavel dentro do turno principal, diferenciando atividade principal e auxiliar sem expor logs brutos.

---

### User Story 3 - Adaptar Catalogo, Providers E Autenticacao Visivel (Priority: P2)

Como administrador ou demonstrador, quero que novos modelos, providers, onboarding e autenticacao de providers sejam apresentados somente em superficies administrativas autorizadas e compreensiveis, para evitar escolhas indisponiveis, confusao de credenciais ou exposicao de detalhes sensiveis.

**Why this priority**: As releases 0.25.0 a 0.27.0 incluem novos providers/modelos, onboarding de provider, proxy local autenticado por OAuth e hardening de clientes. O CappyCloud ja possui catalogo autorizado, administracao de providers e custos; a UI deve continuar governando disponibilidade e seguranca.

**Independent Test**: Pode ser testado abrindo o catalogo/model picker como usuario comum e as telas administrativas como administrador; usuarios comuns veem apenas disponibilidade governada pelo catalogo, enquanto administradores veem onboarding/OAuth e estados de autenticacao.

**Acceptance Scenarios**:

1. **Given** um novo modelo upstream existe, **When** ele ainda nao foi autorizado no CappyCloud, **Then** usuarios finais nao conseguem seleciona-lo.
2. **Given** um provider exige autenticacao ou configuracao adicional, **When** o administrador revisa o status, **Then** a UI administrativa mostra o estado de forma clara sem exibir segredos.
3. **Given** um usuario comum encontra um modelo/provider indisponivel, **When** ele tenta selecionar ou usar esse recurso, **Then** a UI nao mostra onboarding/OAuth e comunica indisponibilidade conforme o catalogo autorizado.
4. **Given** uma conversa usa um modelo com contagem/contexto/custo alterados pelo upgrade, **When** o turno termina, **Then** a UI mostra modelo final, uso e custo coerentes com a governanca do CappyCloud.

---

### User Story 4 - Decidir O Que Nao Vira UI Do Produto (Priority: P3)

Como pessoa responsavel por produto, quero registrar quais novidades do OpenClaude nao devem aparecer no CappyCloud, para evitar levar comandos, mascotes, branding ou fluxos de terminal para uma experiencia web corporativa sem necessidade.

**Why this priority**: Algumas novidades sao pensadas para terminal ou branding upstream. O CappyCloud deve absorver melhorias de runtime sem transformar cada recurso terminal-only em uma nova tela.

**Independent Test**: Pode ser testado revisando a lista de novidades e confirmando que cada item fora de escopo tem justificativa e nao cria requisito visual oculto.

**Acceptance Scenarios**:

1. **Given** uma feature promocional, estetica ou exclusiva de terminal, **When** a equipe avaliar o upgrade, **Then** ela e marcada como fora de escopo ou runtime-only.
2. **Given** uma melhoria de status do terminal tem equivalente util para o chat web, **When** ela for aceita, **Then** a spec descreve o estado de usuario que precisa aparecer, nao o comando original.

### Edge Cases

- A imagem de producao pode estar em 0.24.0 enquanto o Dockerfile local ainda aponta para versao anterior; a fonte de verdade do planejamento deve registrar o runtime observado e o alvo escolhido.
- Releases mais novas podem sair durante o planejamento; o alvo desta spec fica congelado em OpenClaude 0.27.0, e mudancas posteriores exigem nova decisao explicita.
- Melhorias de token/contexto podem divergir do custo real retornado pelo provider; a UI deve diferenciar contagem indicativa de custo persistido.
- Subagents ou sessoes auxiliares podem gerar muitos eventos; a UI deve evitar poluir a conversa principal ou travar a leitura.
- Provider onboarding e OAuth podem exigir fluxo externo; a UI deve comunicar estados pendente, autenticado, erro e expirado sem guardar ou revelar segredo.
- Novos providers/modelos upstream podem nao estar liberados para todos os usuarios, ambientes ou clientes.
- Ferramentas longas podem ficar ativas por varios minutos; o usuario precisa ver continuidade, cancelamento e erro final.
- Recursos visuais upstream, como mascotes, logos ou identidade do OpenClaude, nao devem substituir a identidade do CappyCloud.

## Requirements *(mandatory)*

### Release UI Impact Scope

| Release theme | CappyCloud UI decision | Reason |
|---|---|---|
| 0.25.0 buddy companions and upstream branding | Fora de escopo visual | Recurso estetico/terminal-only nao deve substituir a identidade do CappyCloud. |
| 0.25.0 GPT-5.6/Codex/OpenAI Responses support | Validar catalogo/model picker | Modelos e provider paths so aparecem quando cadastrados e autorizados no CappyCloud. |
| 0.25.0 first-run provider onboarding | Adaptar admin/provider UI se habilitado | Apenas administradores devem ver configuracao pendente, sucesso e erro sem expor credenciais. |
| 0.25.0 token optimization and configurable compaction | Validar chat/context UI | O usuario precisa entender continuidade, compactacao e limites de contexto sem perder historico visivel. |
| 0.25.0 live context bar/token count | Adaptar indicador discreto de contexto | A UI deve mostrar contexto/processamento durante a execucao de forma discreta, sem valor financeiro e sem substituir custo real. |
| 0.25.0 new providers and context variants | Validar catalogo/admin | Entradas upstream nao podem ficar selecionaveis antes de autorizacao e precificacao. |
| 0.26.0 long-running tools stay active | Validar chat activity | Turnos longos devem mostrar atividade viva, cancelamento e falha final sem erro prematuro. |
| 0.26.0 streaming token counts earlier | Adaptar ou validar feedback de streaming | Contagem em tempo real deve ser apresentada como progresso, nao como custo final. |
| 0.26.0 AI/ML API hardening | Validar provider error UI | Erros de formato/autenticacao devem ser claros para admin e sanitizados para usuarios. |
| 0.26.0 Windows/root path handling | Runtime/operacao | Nao exige UI nova, mas erros de path devem continuar compreensiveis quando chegarem ao chat. |
| 0.26.0 slash-command argument handling | Fora de escopo direto | Comandos de terminal nao viram UI web salvo quando houver equivalente no chat. |
| 0.27.0 auth-ready loopback proxy hosts | Adaptar admin/provider auth UI se habilitado | Apenas administradores devem ver fluxos autenticados, estado e proximo passo com seguranca. |
| 0.27.0 new Ling/Macaron catalog entries | Validar catalogo/model picker | Novos modelos devem seguir autorizacao, capacidade, contexto e preco do CappyCloud. |
| 0.27.0 refreshed OpenClaude web identity | Fora de escopo visual | A identidade visual do produto continua sendo CappyCloud. |
| 0.27.0 subagents from multi-repository parent sessions | Adaptar chat activity agrupada | Atividade auxiliar deve aparecer agrupada e colapsavel dentro do turno principal, associada a conversa/repositorios corretos. |
| 0.27.0 tool-failure guard, permission timeout, stats and status UI | Adaptar/validar chat diagnostics | Falhas e timeouts devem virar mensagens acionaveis, sanitizadas e sem duplicar eventos. |

### Functional Requirements

- **FR-001**: System MUST target OpenClaude 0.27.0 for this feature; versions released after 2026-08-06 require a new explicit product decision before entering this scope.
- **FR-002**: System MUST treat the observed production baseline as OpenClaude 0.24.0 and document any mismatch between local build files, production images and the intended target before planning is approved.
- **FR-003**: System MUST classify all user-visible release themes from 0.25.0, 0.26.0 and 0.27.0 as UI adaptation, existing UI validation, runtime/operation only or outside CappyCloud scope.
- **FR-004**: System MUST preserve the CappyCloud chat timeline as the visible source of truth for messages, tool activity, subexecution activity, permission prompts, cancellation, final status, selected repositories, selected model, usage and cost.
- **FR-005**: Users MUST be able to distinguish active long-running work, stalled work, canceled work, permission timeout and final failure without reading raw runtime logs.
- **FR-006**: System MUST show tool errors, runtime guards and permission timeouts as actionable, sanitized states that do not expose provider secrets, hidden prompts, raw command input, raw container logs or repository content beyond authorized message output.
- **FR-007**: System MUST expose live token/context visibility as a discrete execution-time indicator labeled as context/progress information, without financial value and without replacing final provider usage or cost.
- **FR-008**: System MUST keep model/provider selection governed by the CappyCloud authorized catalog, including new upstream models, provider entries, context variants and provider-specific capabilities.
- **FR-009**: Administrators MUST be able to identify provider configuration states relevant to the upgrade, including not configured, credential required, authentication pending, authenticated, failed and disabled, when those states are applicable.
- **FR-010**: System MUST prevent upstream onboarding, OAuth or proxy-auth behavior from making a provider or model visible to unauthorized users.
- **FR-010a**: System MUST expose provider onboarding, OAuth and provider authentication states only to authorized administrators; regular users must see only catalog-governed availability or unavailability.
- **FR-011**: System MUST retain CappyCloud branding and visual language; upstream OpenClaude branding, mascot and terminal-only visual features MUST NOT appear in the product unless explicitly approved in a later design decision.
- **FR-012**: System MUST show subagent or auxiliary-session activity as grouped, collapsible activity inside the parent turn when the runtime exposes it, including relationship to the parent conversation, repository context and terminal status.
- **FR-013**: System MUST validate existing UI states for chat loading, streaming, tool start/result/error, long-running work, permission request, permission timeout, cancellation, retry, compacted/resumed context, usage/cost display and final error.
- **FR-014**: System MUST validate existing admin/model states for provider unavailable, model unauthorized, model retired, provider auth pending, provider auth failed, no authorized models and pricing/capability unknown.
- **FR-015**: System MUST document which UI changes are required before upgrade, which can ship as validation-only, and which are intentionally deferred.
- **FR-016**: System MUST exclude production deployment from this feature and provide a rollout/rollback runbook for later execution after local validation.

### Key Entities *(include if feature involves data)*

- **OpenClaude Release Target**: Verified upstream release selected for the runtime update, including version, date and commit evidence.
- **Runtime Baseline**: Version currently observed in the CappyCloud environment used as the starting point for impact analysis.
- **Release Theme**: A grouped upstream change that may affect CappyCloud users, administrators, runtime behavior or product UI.
- **UI Impact Decision**: Classification of a release theme as UI adaptation, existing UI validation, runtime/operation only or outside CappyCloud scope.
- **Chat Activity State**: Visible state in the conversation timeline for streaming, tool execution, grouped collapsible subexecution, waiting, cancellation, timeout and final result.
- **Provider Auth State**: Administrator-only status of a provider connection or authentication flow.
- **Context Visibility Indicator**: discrete execution-time user-facing representation of context processing, token use or compaction status, never presented as final cost.
- **Model Catalog Entry**: Authorized model visible in CappyCloud, with capability, context, status, provider and cost behavior governed by CappyCloud.

### Runtime Context, Security & Evidence *(mandatory when applicable)*

- **RC-001**: External evidence reviewed on 2026-08-06: OpenClaude changelog reports current version 0.27.0 and highlights releases 0.25.0, 0.26.0 and 0.27.0 at `https://openclaude.gitlawb.com/changelog/`.
- **RC-002**: External evidence reviewed on 2026-08-06: Git tag lookup returned 0.24.0 at `2ff93a10bf88ab6d7030fc4ade5316a7424fa2f9`, 0.25.0 at `0a9bc187a469d492c20fe41d18f75ce693fe2898`, 0.26.0 at `a3c251f77fbbaece6d95052bada597b9380f9fd2`, and 0.27.0 at `7eeb90fb5bc970776e8f8acef2a2d41ff457865f`.
- **RC-003**: External evidence reviewed on 2026-08-06: npm metadata for `@gitlawb/openclaude` returned latest version 0.27.0.
- **RC-004**: Repository/project evidence: previous OpenClaude UI debt spec under `specs/004-openclaude-v017-ui-debt/spec.md` established that CappyCloud owns visible conversation state, model authorization, cost, fallback notices and sanitized diagnostics.
- **RC-005**: Repository/project evidence: active chat-centered UI spec under `specs/007-chat-centered-ui-theme/spec.md` requires the authenticated chat to remain the primary surface, with unified theme, Portuguese user-facing text and admin surfaces layered over the chat experience.
- **RC-006**: Operational evidence from prior production check in this thread observed production sandbox package version 0.24.0 at commit `2ff93a10bf88ab6d7030fc4ade5316a7424fa2f9`; planning must re-check this before implementation if the environment changes.
- **RC-007**: Security boundaries apply to provider credentials, OAuth/auth proxy state, model authorization, repository visibility, tool inputs, command outputs, hidden prompts and raw runtime logs. Any UI adaptation must sanitize sensitive details.
- **RC-008**: Sandbox image build, local patch audit and local validation are in scope. Production deployment is excluded from this feature; a rollout/rollback runbook must be delivered for later execution.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of release themes from OpenClaude 0.25.0 through 0.27.0 have a documented CappyCloud UI impact decision before implementation planning starts.
- **SC-002**: 100% of UI adaptation items have at least one independently testable user-facing acceptance scenario before task generation.
- **SC-003**: During validation, users can identify long-running work, permission timeout, cancellation and final failure states in under 10 seconds without reading logs.
- **SC-004**: In tested conversations, chat timeline, selected repositories, selected model, usage and cost remain consistent in 100% of normal, resumed, long-running and failed-turn scenarios.
- **SC-005**: 100% of newly exposed provider/model states are hidden from unauthorized users and visible only through authorized catalog or admin surfaces.
- **SC-006**: No newly surfaced diagnostic, tool error, auth state or provider message displays secrets, hidden prompts, raw container logs or unauthorized repository content in reviewed scenarios.
- **SC-007**: 100% of terminal-only or upstream-branding features are explicitly classified as outside scope or mapped to a CappyCloud-native user outcome.
- **SC-008**: The selected runtime target and baseline versions are traceable in 100% of review artifacts used for planning.
- **SC-009**: A reviewer can follow the delivered rollout/rollback runbook to identify production prerequisites, deployment steps, validation checks and rollback trigger points before any production execution.

## Assumptions

- The target for this specification is frozen at OpenClaude 0.27.0 as of 2026-08-06.
- The production baseline to reason from is OpenClaude 0.24.0, based on the prior container inspection in this thread.
- The CappyCloud web chat remains the primary user-facing agent surface; OpenClaude terminal UI features do not automatically become product UI.
- The active chat-centered UI/theme direction from `specs/007-chat-centered-ui-theme` remains authoritative for visual language and navigation placement.
- The CappyCloud model catalog, provider configuration and authorization rules remain authoritative over upstream provider/model availability.
- Live token/context information is exposed as a discrete execution-time indicator and does not replace final usage and cost data.
- Production rollout, image push and automatic container replacement are out of scope for this specification; planning must include a rollout/rollback runbook for later execution after local validation.
