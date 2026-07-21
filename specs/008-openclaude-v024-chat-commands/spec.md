# Feature Specification: OpenClaude v0.24 Chat Commands

**Feature Branch**: `[008-openclaude-v024-chat-commands]`

**Created**: 2026-07-20

**Status**: Draft

**Input**: User description: "Atualizar para a ultima versao do OpenClaude, hoje v0.24.0, avaliar o que precisa mudar na UI e trazer os comandos `/` para o input do chat. O usuario forneceu notas de release de v0.19.0 a v0.24.0 e a base atual do repo ainda referencia v0.17.1."

## Clarifications

### Session 2026-07-20

- Q: Qual deve ser o escopo inicial dos comandos slash no chat? -> A: Expor todos os comandos upstream descobertos, marcando indisponiveis os que nao puderem executar no chat.
- Q: Quando comandos slash executaveis devem pedir confirmacao extra? -> A: Apenas comandos que alteram estado, custo, modelo, contexto, runtime, branch, sessao ou acesso externo exigem confirmacao inline.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Executar comandos slash pelo chat (Priority: P1)

Como pessoa usando o chat do CappyCloud, quero digitar `/` no input da conversa e ver comandos suportados com descricao, argumentos e estado de disponibilidade, para executar acoes do agente sem depender do terminal interativo do OpenClaude.

**Why this priority**: O pedido explicito destaca comandos `/` no input do chat como requisito importante. As releases recentes do OpenClaude ampliam comandos e menus interativos; se o CappyCloud continuar expondo apenas texto livre, usuarios nao conseguem descobrir nem usar esses fluxos no produto web.

**Independent Test**: Pode ser testado abrindo uma conversa, digitando `/`, filtrando sugestoes, escolhendo um comando suportado, preenchendo argumentos quando existirem e confirmando que o chat registra a acao e o resultado esperado.

**Acceptance Scenarios**:

1. **Given** uma conversa ativa com sandbox disponivel, **When** o usuario digita `/` no input vazio, **Then** o chat mostra uma lista de comandos suportados, com nomes, descricoes curtas e indicacao de comandos indisponiveis quando aplicavel.
2. **Given** a lista de comandos aberta, **When** o usuario continua digitando parte do nome ou descricao, **Then** a lista filtra os comandos em tempo perceptivel e preserva o texto digitado.
3. **Given** o usuario seleciona um comando que exige argumentos, **When** o comando e aplicado ao input, **Then** o chat orienta quais argumentos faltam sem enviar uma mensagem incompleta.
4. **Given** o usuario seleciona um comando executavel sem argumentos, **When** confirma o envio, **Then** o comando e enviado como acao de conversa e o resultado aparece na timeline sem duplicar mensagens.
5. **Given** o runtime esta ocupado, aguardando permissao ou sem sandbox pronto, **When** o usuario abre `/`, **Then** comandos sensiveis aparecem bloqueados ou com estado claro em vez de falharem silenciosamente.
6. **Given** o usuario seleciona um comando que altera estado, custo, modelo, contexto, runtime, branch, sessao ou acesso externo, **When** tenta executar, **Then** o chat pede confirmacao inline antes de enviar a acao.

---

### User Story 2 - Atualizar runtime para OpenClaude v0.24.0 com rastreabilidade (Priority: P2)

Como pessoa responsavel pela operacao do agente, quero que o sandbox use a ultima versao validada do OpenClaude e que a revisao upstream fique rastreavel, para receber correcoes recentes sem perder as garantias de seguranca, permissao, custo e historico do CappyCloud.

**Why this priority**: O repo atual fixa o sandbox em `v0.17.1`, enquanto a release mais recente verificada em 2026-07-20 e `v0.24.0`. O salto inclui comandos, provider profiles, repo map, skills locais, web search diagnostics, novos providers, cache, sessao, seguranca, timeout e varias correcoes de stream.

**Independent Test**: Pode ser testado verificando a revisao fixada, reconstruindo a imagem do sandbox, iniciando uma conversa e confirmando que o agente responde com modelo, permissao, uso e custo controlados pelo CappyCloud.

**Acceptance Scenarios**:

1. **Given** o sandbox e reconstruido, **When** a versao do runtime e auditada, **Then** a revisao corresponde ao tag `v0.24.0` verificado e a origem da release esta documentada.
2. **Given** uma conversa com modelo e modo de permissao escolhidos pelo usuario, **When** o runtime executa o turno, **Then** a selecao visivel continua sendo a fonte de verdade do CappyCloud, nao defaults ou menus upstream.
3. **Given** o OpenClaude mudou comportamento interno de cache, sessao, provider ou tool stream, **When** o turno termina, **Then** a UI continua mostrando historico, status, modelo final, tokens e custo corretos para a conversa ativa.

---

### User Story 3 - Decidir impacto de UI de cada release recente (Priority: P3)

Como pessoa planejando a atualizacao, quero uma matriz de impacto visual e operacional para as releases de v0.18.0 ate v0.24.0, para separar o que vira UI, o que e somente runtime, o que precisa de validacao e o que fica fora de escopo.

**Why this priority**: O salto de versao acumula muitas mudancas pequenas. Sem triagem, o time pode implementar telas desnecessarias ou ignorar impactos visiveis em comandos, modelos, providers, skills, busca web, retomada de sessao e mensagens de erro.

**Independent Test**: Pode ser testado comparando a matriz contra as notas de release fornecidas e a release oficial mais recente, confirmando que todos os temas relevantes possuem decisao e criterio de aceite.

**Acceptance Scenarios**:

1. **Given** as notas de release de v0.18.0 a v0.24.0, **When** a triagem estiver completa, **Then** cada tema relevante possui decisao: nova UI, evolucao de UI existente, validacao de regressao, somente runtime/operacao, ou fora de escopo.
2. **Given** um item classificado como nova UI, **When** tarefas forem geradas, **Then** ele aparece ligado a um fluxo independente e verificavel.
3. **Given** um item classificado como fora de escopo, **When** a equipe revisar a decisao, **Then** a justificativa explica por que o comportamento terminal upstream nao deve aparecer no chat web.

### Edge Cases

- O usuario digita `/` no meio de uma mensagem normal; o sistema deve tratar como texto comum salvo quando o padrao escolhido para abertura de comandos for atendido.
- O usuario cola texto que comeca com `/` e contem quebras de linha; o chat deve preservar a intencao e nao abrir fluxo destrutivo automaticamente.
- Dois comandos tem prefixos parecidos, como `/set-context-window` e `/clear-context-window`; a busca deve evitar selecao ambigua.
- Um comando upstream existe apenas em terminal interativo, menu TUI, OAuth local ou ambiente remoto sem equivalente headless; ele deve aparecer como indisponivel no catalogo, com motivo em portugues, sem execucao automatica.
- Um comando exige permissao, troca de modelo, web search ou alteracao de configuracao; a UI deve aplicar autorizacao e feedback antes de executar.
- Comandos somente de leitura ou diagnostico podem executar sem confirmacao extra quando autorizados; comandos que alteram estado, custo, modelo, contexto, runtime, branch, sessao ou acesso externo devem pedir confirmacao inline.
- O runtime retorna erro de comando, provider ou tool com detalhes sensiveis; a timeline deve exibir mensagem util e sanitizada.
- O usuario troca de conversa com sugestoes `/` abertas; o input e a lista devem refletir somente a conversa ativa.
- A lista de comandos pode vir de versao diferente do runtime durante deploy parcial; a UI deve degradar para comandos conhecidos e mostrar estado de indisponibilidade.

## Requirements *(mandatory)*

### Release Impact Scope

| Release theme | CappyCloud decision | User-facing expectation |
|---|---|---|
| v0.18.0 session-scoped `/goal` | Nova UI de comando | Expor quando houver contrato headless seguro; mostrar estado de objetivo da sessao sem substituir o historico CappyCloud. |
| v0.18.0 fallback model for interactive sessions | Validar modelo/custo existentes | Fallback deve respeitar catalogo autorizado e aparecer como modelo final quando houver troca. |
| v0.18.0 OpenGateway auto smart-routing model | Validar catalogo/model picker | Modelos automaticos so aparecem quando autorizados pelo ambiente. |
| v0.18.0 provider Atlas Cloud e GitHub Copilot models | Somente catalogo/admin se habilitado | Nao adicionar ao chat sem cadastro, autorizacao e preco/capacidade confiaveis. |
| v0.18.0 HISTORY_SNIP e contexto | Validar continuidade do chat | Snips e compactacao nao podem ocultar contexto visivel nem custo real. |
| v0.19.0 Vietnamese i18n slash descriptions | Nova UI de comando com i18n futura | A lista de comandos deve suportar descricao localizavel; portugues e padrao do CappyCloud. |
| v0.19.0 `/ctx` e token bars em `/cost` | Nova UI de comando e status | Expor contexto/custo como comandos ou paineis compactos, usando custo real do provedor. |
| v0.19.0 compact model option | Validar configuracao/modelo | Modelo de compactacao nao deve virar custo invisivel nem sobrescrever selecao principal. |
| v0.19.0 redacted diagnostic issue reports | Validar diagnosticos | Erros devem ser acionaveis e sem segredo. |
| v0.19.0 provider NEAR AI e Fireworks | Somente catalogo/admin se habilitado | Seguir autorizacao, capacidade e preco do CappyCloud. |
| v0.20.0 `/update` command | Nova UI restrita/operacional | Pode aparecer somente para administradores ou ambientes permitidos; nao deve atualizar runtime de producao sem plano explicito. |
| v0.20.0 `/bughunter`, `/bughunter-security`, `/bughunter-perf` | Nova UI de comando | Expor como acoes de analise quando o repo ativo e permissao permitirem; resultados entram na timeline. |
| v0.20.0 local background sessions | Nova divida UI/UX | Se adotado, chat deve indicar sessoes em segundo plano, progresso e retomada sem confundir com a conversa ativa. |
| v0.20.0 session replay timeline | Nova divida UI futura | Pode virar visualizacao de auditoria; fora do MVP de comandos se nao houver evento headless suficiente. |
| v0.20.0 project conventions to wiki | Validar governanca | Escrita automatica de memoria/wiki exige permissao e evidencia; nao pode ocorrer sem transparencia. |
| v0.20.0 provider env-file, config dir, credential pool | Validar runtime/security | UI nao exibe segredo; erros de credencial devem ser claros e sanitizados. |
| v0.20.0 context collapse, long-turn visibility, stream hang safety | Validar chat existente | Estados de progresso, inatividade, retry e conclusao devem permanecer compreensiveis. |
| v0.21.0 `/set-context-window` e `/clear-context-window` | Nova UI de comando | Comandos devem ajustar contexto da conversa quando autorizado e mostrar valor atual/limpo. |
| v0.21.0 per-agent step limits and branch command | Nova UI ou bloqueio explicito | Expor apenas se houver contrato seguro; branch/fork de conversa precisa respeitar worktree e permissao. |
| v0.21.0 headless heartbeat, deterministic reports | Validar estados e relatorios | Indicadores de vida e relatorios devem aparecer sem spam na timeline. |
| v0.21.0 Opus 4.8, ClinePass, effort routing | Validar catalogo/model picker | Modelo, contexto, effort e custo devem vir da configuracao autorizada. |
| v0.22.0 captured LSP diagnostics | Nova UI de diagnosticos se disponivel | Mostrar diagnosticos do repo como evidencias compactas, com paths autorizados. |
| v0.22.0 markdown task reports | Nova UI/acao de relatorio | Relatorios gerados devem ser renderizados em markdown seguro na conversa. |
| v0.22.0 grouped branched sessions in resume picker | Nova UI de retomada se adotado | Conversas ramificadas devem aparecer agrupadas sem misturar historicos. |
| v0.22.0 honest feedback pass, retries, hint grace period | Validar chat existente | Retry, truncamento e hints devem ser visiveis e discretos. |
| v0.23.0 repo map codebase intelligence | Nova UI/contexto | Indicar quando mapa de repo foi usado e permitir diagnostico resumido sem despejar arquivo interno. |
| v0.23.0 local skill CLI support and PDF skill | Nova UI/admin de skills | Skills locais devem ser auditaveis e autorizadas; PDF gerado deve aparecer como artefato seguro quando suportado. |
| v0.23.0 smart auto-routing simple-vs-strong | Validar modelo/custo | Auto-routing so pode escolher modelos autorizados e deve expor modelo final/custo. |
| v0.23.0 AI/ML API provider | Somente catalogo/admin se habilitado | Provider novo depende de credencial, preco e permissao. |
| v0.24.0 ultrathink/ultracode effort detection | Nova UI ou indicador | Se palavras-chave alterarem effort, o chat deve mostrar o effort aplicado e permitir controle previsivel. |
| v0.24.0 model-picker inactive provider profiles in `/model` | Nova UI de comando/model picker | `/model` no chat deve mostrar perfis ativos e inativos com motivo e acao segura. |
| v0.24.0 Cloudflare Workers AI provider | Somente catalogo/admin se habilitado | Nao expor sem configuracao e autorizacao. |
| v0.24.0 settings subscription override, per-model context/max output | Nova UI/admin ou validacao | Overrides devem aparecer em configuracao autorizada e refletir no chat. |
| v0.24.0 WebSearch doctor diagnostics | Nova UI de diagnostico | Se busca web for habilitada, `/doctor` ou comando equivalente deve explicar disponibilidade e falha. |
| v0.24.0 OAuth manual callback paste | Fora do chat comum; UI operacional se necessario | Fluxos de autenticacao remota devem ser orientados sem expor callback ou token indevidamente. |
| v0.24.0 footer mounted across slash suggestions | Validar composer | Sugestoes `/` nao podem desmontar toolbar, custo, modelo ou modo de permissao. |
| v0.20.0-v0.24.0 prototype-safe, path, NO_PROXY, timeout, cache and stream fixes | Validar regressao/security | Mensagens devem continuar sanitizadas; path/worktree/timeout nao podem vazar dado sensivel nem travar UI. |

### Functional Requirements

- **FR-001**: System MUST target OpenClaude `v0.24.0` as the next runtime version and keep the upstream tag and commit traceable in planning and validation artifacts.
- **FR-002**: System MUST treat the CappyCloud conversation as the visible source of truth for messages, selected repository, selected model, permission mode, runtime status, token usage and cost.
- **FR-003**: System MUST provide slash command discovery from the chat input when the user starts an eligible command expression with `/`.
- **FR-004**: Slash command suggestions MUST show command name, short Portuguese description, availability state and required argument hints for supported commands.
- **FR-005**: Users MUST be able to filter slash commands by name and description without losing the current draft.
- **FR-006**: Users MUST be able to insert or execute a selected slash command from the input using keyboard and pointer interactions.
- **FR-007**: System MUST prevent incomplete, unsupported or unauthorized commands from being sent as executable actions and MUST explain the reason in user-facing Portuguese.
- **FR-008**: System MUST expose all discovered upstream slash commands in the chat command catalog, while clearly marking commands unavailable when they are terminal-only, unsafe, unauthorized or lack a CappyCloud-safe execution path.
- **FR-009**: System MUST map executable OpenClaude commands to CappyCloud-safe chat actions before allowing execution; unavailable commands MUST remain discoverable with a Portuguese reason and MUST NOT run as plain text or bypass gates.
- **FR-010**: System MUST include at least these command families in the product decision matrix: model selection, context window, cost/context diagnostics, bughunter analysis, task reports, repo map diagnostics, background sessions, goal/session controls, update/runtime operations and doctor diagnostics.
- **FR-011**: `/model` behavior in the chat MUST respect the CappyCloud authorized model catalog, show inactive/unavailable provider profiles when useful, and never select an unauthorized model.
- **FR-012**: Context and cost commands MUST use provider-returned usage and current authorized pricing where available; local estimates may only be marked as estimates.
- **FR-013**: Commands that can change settings, cost, model, context window, runtime version, background execution, branch/session state or external access MUST require inline confirmation and the same authorization gates as equivalent UI controls.
- **FR-014**: System MUST preserve action-required prompts and pending user replies when slash suggestions open or close.
- **FR-015**: System MUST preserve attachments, multiline drafts and pasted content when slash suggestions open, close, filter or insert a command.
- **FR-016**: System MUST keep slash suggestions from hiding or displacing critical composer state, including selected model, permission mode, send/stop action, attachment state and runtime warnings.
- **FR-017**: System MUST display command execution results in the conversation timeline with clear status: started, waiting for input, completed, unavailable, failed or cancelled.
- **FR-018**: System MUST sanitize command errors, diagnostics, provider failures, paths, URLs, OAuth callbacks, tool arguments and logs before rendering them to users.
- **FR-019**: System MUST classify every relevant release theme from v0.18.0 through v0.24.0 as new UI, existing UI evolution, regression validation, runtime/operation only or outside CappyCloud scope before implementation tasks are finalized.
- **FR-020**: System MUST audit existing local OpenClaude patches and document which are retained, changed, removed or obsolete for v0.24.0 before runtime implementation is marked ready.
- **FR-021**: System MUST validate normal answer, streaming text, tool start/result/error, permission prompt, cancellation, retry, timeout, fallback model, inactive model, image attachment, report rendering and command suggestion states before completion.

### Key Entities *(include if feature involves data)*

- **Slash Command**: A named chat action beginning with `/`, with display name, description, argument hints, availability, authorization requirement and execution behavior.
- **Command Suggestion State**: The transient UI state for command discovery, filtering, keyboard focus, selected item, argument guidance and disabled reason.
- **Command Execution Event**: A timeline event representing command start, progress, result, required input, failure, cancellation or unavailable state.
- **Release Delta Theme**: A grouped upstream OpenClaude change between v0.18.0 and v0.24.0, with source release, category and CappyCloud product decision.
- **Agent Runtime Pin**: The selected OpenClaude tag and commit used by the sandbox build.
- **Authorized Model Profile**: A CappyCloud-approved model/provider entry, including active state, capabilities, context window, pricing and default eligibility.
- **Runtime Diagnostic**: Sanitized operational feedback about provider, web search, OAuth, settings, tool execution, timeout, cache, stream or sandbox state.

### Runtime Context, Security & Evidence *(mandatory when applicable)*

- **RC-001**: External release evidence reviewed: GitHub releases page for `Gitlawb/openclaude` showed `v0.24.0` as Latest on 2026-07-20; tag verification returned `refs/tags/v0.24.0` at `2ff93a10bf88ab6d7030fc4ade5316a7424fa2f9`.
- **RC-002**: Release notes provided by the user cover `v0.19.0` through `v0.24.0`; the attached `v0.19.0` text also includes `v0.18.0`. Because repository evidence shows the sandbox currently pinned to `v0.17.1`, this spec scopes the full jump from `v0.18.0` through `v0.24.0`.
- **RC-003**: Repository evidence reviewed: `docs/ARCHITECTURE.md` describes OpenClaude running inside the sandbox over gRPC and records permission mode as conversation configuration sent through the stream.
- **RC-004**: Repository evidence reviewed: `services/sandbox/Dockerfile` currently pins `OPENCLAUDE_REF=1b7e55058cca57f2f83d7e229441631794286c1a`, the previous `v0.17.1` target.
- **RC-005**: Repository evidence reviewed: `proto/openclaude.proto` already carries optional per-request `permission_mode`, and `services/cappycloud_agent/_grpc_session.py` sends sanitized permission mode in each chat request.
- **RC-006**: Repository evidence reviewed: `web/src/pages/ChatPage.tsx` contains the current chat composer, model selector, permission mode control, action-required card, usage/cost display and fallback notice; slash commands must integrate with those states instead of adding a separate terminal surface.
- **RC-007**: Security rules: slash commands must not bypass repository authorization, sandbox worktree guards, permission prompts, model authorization, provider secret redaction, OAuth safety, path validation or external-action confirmation.
- **RC-008**: Sandbox image build, local patch audit, runtime compatibility checks and frontend command UX are in scope. Production rollout, image push, automatic deployment, credential provisioning and enabling new providers for users are out of scope unless later Spec Kit artifacts add them explicitly.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of relevant release themes from v0.18.0 through v0.24.0 have a documented CappyCloud decision before implementation is considered ready.
- **SC-002**: Users can discover supported slash commands from an empty chat input in under 2 seconds after typing `/` in 95% of manual smoke attempts on a normal development machine.
- **SC-003**: Users can execute a supported no-argument slash command from discovery to visible timeline result in under 15 seconds when the sandbox is already ready.
- **SC-004**: 100% of command families exposed in the chat have documented authorization, availability and error states.
- **SC-005**: Slash command suggestions preserve draft text, attachments, selected model and permission mode in 100% of validation scenarios.
- **SC-006**: In command validation scenarios, unauthorized or unavailable commands are blocked before execution in 100% of attempts and show a Portuguese explanation.
- **SC-007**: Normal answer, stream progress, tool activity, action-required, command suggestions, command execution, cancellation, retry, timeout, model fallback, usage and cost each have at least one validation scenario before completion.
- **SC-008**: No command result, diagnostic, OAuth instruction, tool error or provider error renders raw API keys, hidden prompts, OAuth callback payloads, unsanitized tool arguments or unauthorized repository contents.
- **SC-009**: The selected OpenClaude runtime revision is traceable to `v0.24.0` in 100% of build, review and validation artifacts for this feature.

## Assumptions

- The requested "ultima versao" is OpenClaude `v0.24.0`, verified on 2026-07-20; if a newer release appears before implementation, the plan should explicitly decide whether to retarget.
- CappyCloud remains a web chat product; OpenClaude terminal-only commands are not automatically product requirements unless there is a safe headless equivalent.
- Portuguese remains the default language for user-facing CappyCloud UI text.
- The existing model catalog, permission mode, cost accounting and sandbox worktree guard remain authoritative.
- Slash command discovery should include all upstream commands the runtime exposes, but execution should remain gated by CappyCloud-safe mappings, authorization and availability checks.
- New providers mentioned upstream are not enabled for users merely by upgrading the runtime; they require catalog/admin configuration and authorization.
- Runtime update implementation will happen after `/speckit-plan` and `/speckit-tasks`, not in this specification step.
