# Feature Specification: OpenClaude v0.15.0 UI Impact Audit

**Feature Branch**: `[003-openclaude-v015-ui-audit]`

**Created**: 2026-06-17

**Status**: Draft

**Input**: User description: "Atualizar o OpenClaude para v0.15.0 e mapear o que precisa ou nao mudar na UI do CappyCloud, usando as notas da release v0.15.0 de 2026-05-26."

## Clarifications

### Session 2026-06-17

- Q: Como o CappyCloud deve determinar que o aviso de segurança da v0.15.0 se aplica? → A: Mostrar pelo modo configurado na sessão e enriquecer com alerta de runtime quando disponível.
- Q: Onde o risco de permissões permissivas deve aparecer para o usuário? → A: Adicionar seletor por sessão no chat: solicitar permissões, aceitar edições, planejamento, automático, ignorar permissões.
- Q: Qual deve ser o modo padrão de permissões em uma nova sessão? → A: Nova sessão começa em solicitar permissões.
- Q: Quais modos de permissão devem acionar o aviso de risco de bypass? → A: Aviso de risco em modo automático e ignorar permissões; cautela menor em aceitar edições.
- Q: Como classificar provider de terceiros para disparar o aviso de bypass? → A: Não classificar por provider; avisar só pelo modo de permissão.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Atualizar runtime com impacto visual conhecido (Priority: P1)

Como pessoa responsavel pela atualizacao, quero saber exatamente quais itens da release v0.15.0 afetam a UI do CappyCloud, para atualizar o runtime sem criar telas desnecessarias nem ocultar informacao importante.

**Why this priority**: A atualizacao muda comportamento de agentes, modelos, retry, seguranca e stream. Antes de implementar, a equipe precisa de uma decisao revisavel para cada item da release.

**Independent Test**: Pode ser testado revisando a matriz de escopo contra a release v0.15.0 e confirmando que todos os itens possuem decisao: nova UI, validar UI existente ou sem mudanca visual.

**Acceptance Scenarios**:

1. **Given** a lista oficial de features e bug fixes da v0.15.0, **When** a avaliacao for concluida, **Then** 100% dos itens possuem uma decisao de impacto na UI do CappyCloud.
2. **Given** um item classificado como sem mudanca visual, **When** a equipe revisar a spec, **Then** a justificativa explica qual comportamento existente cobre o item ou por que ele pertence apenas ao runtime.
3. **Given** um item classificado como nova UI, **When** a equipe iniciar o planejamento, **Then** o usuario-alvo, a superficie visual e a necessidade de validacao estao claros.

---

### User Story 2 - Controlar modo de permissoes da sessao (Priority: P2)

Como pessoa usando o chat do CappyCloud, quero ver e escolher o modo de permissoes da sessao, para saber quando o agente vai pedir confirmacao, aceitar edicoes, ficar em planejamento, agir automaticamente ou ignorar permissoes.

**Why this priority**: A v0.15.0 adiciona aviso de startup para risco de provider de terceiros com modo permissivo. No CappyCloud, esse risco precisa ser visivel e acionavel no fluxo em que o usuario decide o grau de autonomia da sessao.

**Independent Test**: Pode ser testado abrindo uma conversa, alterando o modo de permissoes e iniciando uma execucao; o chat deve mostrar o modo ativo, aplicar o comportamento escolhido na sessao e exibir aviso quando o modo criar risco de bypass.

**Acceptance Scenarios**:

1. **Given** uma conversa nova, **When** o usuario abre o chat, **Then** ele ve o modo solicitar permissoes ativo para aquela sessao antes de enviar a primeira mensagem.
2. **Given** o usuario altera o modo para solicitar permissoes, aceitar edicoes, planejamento, automatico ou ignorar permissoes, **When** ele envia uma nova mensagem, **Then** o agente usa esse modo ate que o usuario altere novamente ou a sessao termine.
3. **Given** o modo ativo e modo automatico ou ignorar permissoes, **When** o usuario visualiza o seletor, **Then** a UI mostra um aviso claro de bypass junto ao modo ativo.
4. **Given** o modo ativo e aceitar edicoes, **When** o usuario visualiza o seletor, **Then** a UI mostra cautela menor e nao trata esse modo como equivalente a ignorar permissoes.
5. **Given** o runtime tambem reporta o alerta de startup do OpenClaude, **When** o usuario revisa o aviso, **Then** a UI indica que o risco foi confirmado pelo runtime sem mostrar API keys, prompts ocultos ou detalhes sensiveis.

---

### User Story 3 - Manter o chat estavel apos a atualizacao (Priority: P3)

Como pessoa usando o chat do agente, quero que mensagens, tools, prompts de acao, custo, modelo e diagnosticos existentes continuem claros apos a atualizacao, para nao confundir mudanca interna com regressao visual.

**Why this priority**: A maior parte da v0.15.0 corrige comportamento interno. O usuario final deve perceber melhora de estabilidade, nao novos componentes sem necessidade.

**Independent Test**: Pode ser testado com cenarios controlados de tool call, erro de tool, action-required, conclusao normal, diagnostico de payload, custo e uso.

**Acceptance Scenarios**:

1. **Given** uma tool inicia e recebe argumentos completos apenas no fim do stream, **When** o evento aparece no chat, **Then** a linha de atividade existente mostra dados coerentes e nao perde o input da tool.
2. **Given** o usuario escolhe um modelo no CappyCloud, **When** o agente ou subagent executa com override permitido, **Then** o modelo mostrado e cobrado no turno continua consistente com a selecao ou configuracao aplicavel.
3. **Given** skills ou settings sao recarregadas em rajadas, **When** o agente continua a conversa, **Then** a UI nao mostra duplicidade, flicker ou erro visual causado por reloads repetidos.

### Edge Cases

- A tag v0.15.0 pode exigir ajuste de patches locais antes do runtime iniciar; a UI nao deve ser considerada pronta se o sandbox nao sobe.
- O aviso de seguranca pode existir apenas em log upstream; o CappyCloud precisa preservar o valor do aviso para operadores sem depender de acesso ao container.
- A configuracao cadastrada, o modo escolhido na sessao e o alerta observado no runtime podem divergir temporariamente; a UI deve preferir exibir o aviso pelo modo da sessao e apenas usar o runtime como contexto adicional.
- O usuario pode mudar o modo no meio da conversa; a mudanca deve afetar novas execucoes sem alterar retroativamente o historico de turnos anteriores.
- Uma nova sessao nao deve herdar automaticamente o ultimo modo usado pelo usuario nem um modo permissivo do sandbox; o default visivel deve ser solicitar permissoes.
- Parametros legados de auto-aprovacao global do sandbox nao devem continuar ativos como fallback silencioso; se existirem em ambiente antigo, devem ser ignorados, removidos ou explicitamente documentados como obsoletos.
- Aceitar edicoes e permissivo, mas nao deve receber o mesmo aviso de bypass usado para modo automatico ou ignorar permissoes; deve receber uma indicacao visual de cautela menor.
- A UI nao deve tentar classificar provider de terceiros para decidir a severidade do aviso; essa severidade vem apenas do modo de permissao da sessao.
- A feature upstream de "active session agent" pertence ao menu interativo do OpenClaude; no CappyCloud ela so deve virar UI se houver controle real e util no fluxo headless usado pelo produto.
- Perfis/modelos upstream podem nao coincidir com o catalogo de modelos do CappyCloud; a UI deve continuar usando o catalogo autorizado do ambiente.
- Mudancas de retry, credenciais, JSON schema, compactacao e watchers podem melhorar o comportamento sem criar novo elemento visual.

## Requirements *(mandatory)*

### Release Item UI Scope

| Release item v0.15.0 | CappyCloud UI decision | Reason |
|---|---|---|
| agents: set active session agent from agents menu | Sem mudanca imediata na UI do CappyCloud | A mudanca upstream e do menu interativo do OpenClaude. O CappyCloud hoje cadastra subagents em area admin e injeta perfis de repo automaticamente; a superficie headless atual nao expoe selecao de agente ativo no contrato de chat. |
| configure API retry backoff | Sem nova UI de usuario | E configuracao operacional de retry. Deve ser validada no runtime e documentada, mas o chat deve mostrar apenas progresso normal ou erro final acionavel. |
| query: robust multi-lingual and structural continuation nudge | Validar UI existente | Melhora continuidade de resposta. O chat existente deve continuar renderizando texto e estados finais sem novo componente. |
| safety: warn at startup when 3P provider + permissive mode skip the AI classifier | Nova UI no chat para modo de permissoes e aviso de risco | O CappyCloud roda OpenClaude headless; a UI deve avisar pelo modo de permissao escolhido, sem tentar classificar provider, e pode adicionar contexto quando o runtime reportar o alerta upstream. |
| agent: allow custom model overrides | Validar UI existente | O CappyCloud ja possui picker de modelo no chat e campo de modelo em subagents globais. A validacao deve confirmar que overrides permitidos continuam visiveis e coerentes. |
| attribution: make git attribution opt-in by default | Sem nova UI | Afeta identidade/atribuição Git no runtime. Validar comportamento operacional, nao chat. |
| codex-stream: recover tool args delivered only via done events | Validar UI existente | A timeline de tools ja mostra input/output por tool. A validacao deve garantir que argumentos recuperados aparecam corretamente. |
| codex: allow credential storage fallback | Sem nova UI | Fallback de credenciais e interno; falha final segue o tratamento de erro ja existente. |
| json-schema: support top-level non-object roots via wrap/unwrap | Sem nova UI | Corrige saida estruturada interna; erro final segue tratamento comum se ocorrer. |
| model: include profile models in descriptor picker | Sem nova UI do CappyCloud | O picker do CappyCloud usa catalogo autorizado do ambiente, nao o descriptor picker interativo do OpenClaude. |
| route MiniMax compacting through Anthropic-compatible API | Sem nova UI | E roteamento interno de provider/compactacao. Chat deve manter comportamento atual. |
| watchers: debounce skills and settings reload bursts | Validar UI existente | Admin de skills/agents e chat nao devem mostrar duplicidade ou instabilidade durante reloads. |

### Functional Requirements

- **FR-001**: System MUST update the agent runtime target to OpenClaude v0.15.0 and keep the selected upstream revision traceable.
- **FR-002**: System MUST classify every v0.15.0 release item as new CappyCloud UI, validation of existing CappyCloud UI, or no CappyCloud UI change.
- **FR-003**: Users MUST be able to see and change the permission mode for the active chat session before starting a new agent execution.
- **FR-003a**: System MUST support these session permission modes: solicitar permissoes, aceitar edicoes, modo de planejamento, modo automatico, and ignorar permissoes.
- **FR-003b**: System MUST apply the selected permission mode to new executions in that session until the user changes it or the session ends.
- **FR-003c**: System MUST show a high-risk bypass warning beside the session permission mode when modo automatico or ignorar permissoes is active.
- **FR-003d**: System MUST determine warning severity from the CappyCloud session permission mode, without classifying providers, then add runtime context when the OpenClaude startup alert is available.
- **FR-003e**: System MUST start every new chat session in solicitar permissoes mode by default.
- **FR-003f**: System MUST show a lower-severity caution indicator, not the high-risk bypass warning, when aceitar edicoes is active.
- **FR-004**: The safety warning MUST avoid exposing provider secrets, hidden prompts, repository contents, tool inputs, or raw container logs.
- **FR-005**: Users MUST continue seeing existing chat treatments for text, tool activity, tool results, action-required prompts, payload diagnostics, model used, token usage, cost, cancellation, and errors.
- **FR-006**: System MUST keep OpenClaude terminal-menu-only changes out of the CappyCloud chat unless they expose a real user choice in the CappyCloud conversation flow.
- **FR-007**: System MUST preserve CappyCloud model authorization and catalog behavior when OpenClaude model/profile fixes are adopted.
- **FR-008**: System MUST document which local OpenClaude patches are retained, changed, removed, or made obsolete by v0.15.0 before implementation is marked ready.
- **FR-009**: System MUST provide a reviewable UI-scope outcome so reviewers can confirm that no release item was skipped.
- **FR-010**: System MUST remove or neutralize legacy process-wide permission/auto-approval parameters so the per-session permission mode is the only active source of OpenClaude permission behavior.

### Key Entities *(include if feature involves data)*

- **Release Item**: One feature or bug fix from OpenClaude v0.15.0, with title, category, source link, and UI scope decision.
- **UI Scope Decision**: Classification for a release item: new CappyCloud UI, validation of existing CappyCloud UI, or no CappyCloud UI change.
- **Session Permission Mode**: The selected autonomy level for one chat session, with values for requesting permissions, accepting edits, planning only, automatic execution, or ignoring permissions. New sessions default to requesting permissions.
- **Session Permission Warning**: User-facing operational warning shown when the active session permission mode creates or approaches classifier-bypass risk. Modo automatico and ignorar permissoes use a high-risk bypass warning; aceitar edicoes uses a lower-severity caution indicator. The warning is derived from the session mode and may include runtime context when the sandbox reports the upstream startup alert.
- **Agent Runtime Pin**: Traceable OpenClaude version and upstream revision selected for the sandbox build.
- **Agent Visual State**: Existing chat or admin visual treatment that must remain stable, including tool activity, action-required prompts, diagnostics, model labels, usage, cost, and sandbox status.

### Runtime Context, Security & Evidence *(mandatory when applicable)*

- **RC-001**: External release evidence reviewed: GitHub release `v0.15.0` published on 2026-05-26 lists 4 features and 8 bug fixes at https://github.com/Gitlawb/openclaude/releases/tag/v0.15.0. Tag lookup on 2026-06-17 returned `refs/tags/v0.15.0` at `670744fc70353f2270e86531dffa1c06f4fac79c`.
- **RC-002**: Repository evidence reviewed: `docs/ARCHITECTURE.md` describes OpenClaude running inside the sandbox via gRPC; `services/sandbox/Dockerfile` currently pins OpenClaude v0.14.0; `proto/openclaude.proto` carries the internal chat stream contract; `web/src/pages/ChatPage.tsx` renders model, usage, cost, tools, action-required prompts, and payload diagnostics.
- **RC-003**: Security behavior is product-visible when a sandbox uses provider keys, repository context, skills, MCP settings, and permissive session modes. The UI warning severity is based on the selected permission mode, not provider classification. Any warning or diagnostic must be sanitized before reaching the UI.
- **RC-004**: Sandbox image build and patch audit are in scope. Production rollout, image push, Portainer/Swarm deployment, and automatic container replacement are out of scope for this specification unless explicitly added in a later plan.
- **RC-005**: Legacy sandbox parameters such as global auto-approval environment defaults are cleanup targets. They must not remain as active hidden behavior after request-scoped permission mode is introduced.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of OpenClaude v0.15.0 release items have a documented CappyCloud UI decision before implementation planning starts.
- **SC-002**: In a risky permission mode, a user can identify the active mode and related safety warning in under 10 seconds from the chat, regardless of whether runtime context has already been collected.
- **SC-003**: In non-risky permission modes, the high-risk bypass warning has 0 false-positive appearances across tested cases.
- **SC-004**: Existing chat states for normal answer, tool activity, tool error, action-required prompt, payload diagnostics, model label, usage, cost, cancellation, and error each have at least one validation scenario before completion.
- **SC-005**: No UI warning or diagnostic introduced by this update displays raw secrets, provider API keys, hidden prompts, repository file contents, or raw container logs.
- **SC-006**: The selected OpenClaude runtime revision is traceable to the v0.15.0 tag in 100% of build/review artifacts.
- **SC-007**: Active sandbox/runtime startup paths contain no legacy process-wide auto-approval default that can override the per-session mode.

## Assumptions

- The requested scope is updating the CappyCloud OpenClaude runtime and mapping UI impact, not deploying the updated sandbox to production.
- The CappyCloud chat remains the primary user-facing agent surface; OpenClaude terminal UI features do not automatically become CappyCloud UI requirements.
- The expected new CappyCloud UI from v0.15.0 is a chat-level session permission mode selector with warnings derived from the selected mode.
- Existing v0.14.0 payload diagnostics remain part of the chat and should not be redesigned as part of this update.
- Runtime retry/backoff settings can be configured operationally first; a dedicated admin tuning UI is outside this release unless planning finds an existing product requirement for it.
