# Feature Specification: OpenClaude v0.14.0 Chat Visual Upgrade

**Feature Branch**: `[002-openclaude-visual-upgrade]`

**Created**: 2026-06-17

**Status**: Draft

**Input**: User description: "Atualizar a versao do openclaude para v0.14.0 e analisar quais features e bug fixes precisam ter recursos visuais no chat da UI."

## Clarifications

### Session 2026-06-17

- Q: O breakdown de tamanho do payload deve aparecer apenas durante o stream ou ficar disponivel no historico do turno?-> A: Mostrar e persistir no turno do chat, disponivel tambem ao recarregar a conversa.
- Q: Como o breakdown deve aparecer visualmente no turno do chat?-> A: Resumo compacto sempre visivel quando houver diagnostico, com detalhes recolhidos e expansiveis.
- Q: Quais informacoes devem aparecer no resumo compacto do breakdown?-> A: Total e tres maiores categorias; expansao mostra todas as categorias seguras disponiveis.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Entender peso do pedido no chat (Priority: P1)

Como pessoa usando o chat do agente, quero ver uma explicacao clara do tamanho do pedido quando o agente disponibilizar essa informacao, para entender por que uma execucao pode ficar cara, lenta ou perto do limite.

**Why this priority**: A novidade de diagnostics sobre decomposicao de tamanho do payload e a unica mudanca da v0.14.0 que cria valor direto no chat e nao existe hoje como sinal visual especifico.

**Independent Test**: Pode ser testado com uma conversa que inclua mensagem, contexto de repositorio e anexos; o chat deve mostrar uma decomposicao compreensivel do peso do pedido sem exigir leitura de logs.

**Acceptance Scenarios**:

1. **Given** uma execucao do agente com diagnostico de tamanho do pedido disponivel, **When** o turno aparece no chat, **Then** o usuario ve um resumo compacto com o total e as tres maiores categorias do payload.
2. **Given** uma execucao sem diagnostico de tamanho do pedido, **When** o turno aparece no chat, **Then** a conversa continua sem espaco vazio, erro visual ou texto tecnico incompleto.
3. **Given** um payload com anexos ou contexto grande, **When** a decomposicao for exibida, **Then** a UI destaca os maiores componentes com linguagem acessivel e sem expor segredos.
4. **Given** uma conversa recarregada depois da execucao, **When** o turno possuir diagnostico de tamanho do payload, **Then** o breakdown continua disponivel no historico daquele turno.
5. **Given** um usuario quer entender o detalhe completo do diagnostico, **When** ele expande o resumo compacto, **Then** a UI mostra os componentes detalhados disponiveis para aquele turno.

---

### User Story 2 - Validar estabilidade visual dos estados existentes (Priority: P2)

Como pessoa usando o chat, quero que timeouts, erros de ferramenta, pedidos de acao humana e retomadas continuem claros durante a atualizacao, para nao confundir bug corrigido com falha nova da interface.

**Why this priority**: A maior parte da v0.14.0 corrige comportamento interno, mas esses comportamentos passam pelo chat como progresso, ferramenta, erro ou acao requerida.

**Independent Test**: Pode ser testado com eventos simulados ou uma conversa controlada que gere timeout, erro de tool, pedido de confirmacao e retomada; cada estado deve usar os componentes visuais ja esperados.

**Acceptance Scenarios**:

1. **Given** uma ferramenta termina com erro e inclui stdout capturado, **When** o resultado aparece na linha de atividade, **Then** o usuario consegue expandir e ler a saida relevante.
2. **Given** o agente fica sem responder ate o limite de seguranca, **When** o timeout ocorre, **Then** o chat sai do estado de espera infinita e mostra erro acionavel.
3. **Given** o agente pede confirmacao ou informacao, **When** o evento chega ao chat, **Then** a UI mostra controles claros para responder e nao permite duplo envio acidental.
4. **Given** uma conversa retomada apos compactacao, **When** houver blocos de raciocinio ou atividade preservados, **Then** o historico visual nao mostra resultado antigo como se fosse novo.

---

### User Story 3 - Separar mudancas sem impacto visual no chat (Priority: P3)

Como pessoa preparando a atualizacao, quero uma classificacao objetiva de cada item da release, para nao criar trabalho visual desnecessario nem ignorar algo que o usuario final deveria ver.

**Why this priority**: A release mistura diagnostico, autenticacao, OAuth, providers, entrada de texto, tools e XML; nem tudo pertence ao chat.

**Independent Test**: Pode ser testado revisando a matriz de escopo contra a release v0.14.0 e confirmando que cada item tem decisao: novo visual, validacao visual existente ou sem recurso visual no chat.

**Acceptance Scenarios**:

1. **Given** a lista de features e bug fixes da v0.14.0, **When** a avaliacao for concluida, **Then** cada item tem uma decisao de escopo visual e uma justificativa.
2. **Given** um item classificado como sem impacto visual no chat, **When** a equipe revisar a spec, **Then** a justificativa explica onde o impacto deve ser validado fora do chat ou por comportamento interno.

### Edge Cases

- O diagnostico de payload pode estar ausente em alguns providers, modelos ou fluxos de erro; a UI deve degradar sem quebrar a conversa.
- A decomposicao pode conter nomes de arquivos, paths, tool inputs ou metadados sensiveis; o chat deve mostrar apenas categorias e tamanhos seguros.
- A atualizacao pode alterar a forma de tool output ou thinking blocks; o chat deve evitar duplicar atividade, mostrar saida antiga como nova ou manter spinner preso.
- Providers nao OpenAI e xAI/Grok podem estar configurados no ambiente, mas isso nao deve criar elementos novos no chat sem que o modelo selecionado ou o erro do turno exija contexto para o usuario.

## Requirements *(mandatory)*

### Release Item Visual Scope

| Release item v0.14.0 | Chat visual decision | Reason |
|---|---|---|
| diagnostics: request payload size breakdown | Novo recurso visual no chat | Cria informacao nova, util para usuario entender peso, custo e limite do turno. |
| opengateway: API key em `/v1/*` e bearer auth | Sem novo recurso visual no chat | E regra de autenticacao de gateway; no chat deve aparecer apenas erro comum se a chamada falhar. |
| xAI/Grok OAuth provider | Sem novo recurso visual no chat | E configuracao de provider/modelo; o chat ja mostra modelo selecionado e uso. |
| QueryGuard com timeout de 5 minutos | Validar visual existente | Deve encerrar espera infinita e usar estado de erro/progresso ja existente. |
| Non-OpenAI providers sem `OPENAI_API_KEY` | Sem novo recurso visual no chat | Corrige validacao de ambiente; sucesso ou erro ja passam pelo fluxo normal. |
| Bash preserva stdout em erro | Validar visual existente | Saida de tool com erro deve continuar expansivel e legivel. |
| Compactacao limpa native tool results | Validar visual existente | Evita artefato visual antigo no historico apos compactacao. |
| Built-in agents registrados para Agent tool | Validar visual existente | Quando Agent tool for usada, deve aparecer como tool normal; nao exige componente proprio. |
| Harden XAA OAuth callback state | Sem novo recurso visual no chat | E seguranca de callback OAuth fora da conversa. |
| Input preserva keypress UTF-8 dividido | Sem novo recurso visual no chat | Deve preservar texto digitado; nao cria elemento visual novo. |
| MiMo remove campos nao suportados e preserva reasoning | Validar visual existente | Se reasoning chegar no stream, deve usar a linha de atividade existente. |
| Monitor fecha dialog de permissao apos selecao | Validar visual existente | Pedidos de permissao ja usam cartao de acao humana quando chegam ao chat. |
| Query para loops repetidos de tool failure | Validar visual existente | Deve evitar repeticao visual de erros e encerrar com mensagem clara. |
| Recovery mantem thinking blocks no resume | Validar visual existente | Historico/atividade retomada deve continuar coerente sem novo componente obrigatorio. |
| Retry ajusta max tokens em 402 do OpenRouter | Sem novo recurso visual no chat | Retentativa pode ser invisivel; erro final usa tratamento existente se falhar. |
| stdin/MCP evita input freeze | Sem novo recurso visual no chat | Corrige travamento operacional; o chat deve permanecer interativo. |
| TaskListV2 mostra labels | Sem novo recurso visual no chat | E visual do openclaude TUI, nao da UI de chat CappyCloud. |
| Read.pages em branco tratado como omitido | Sem novo recurso visual no chat | Corrige comportamento de tool Read; resultado segue tool output normal. |
| XML escape aceita null/undefined | Sem novo recurso visual no chat | Corrige serializacao interna; erro final segue tratamento comum se ocorrer. |

### Release Item Implementation Outcomes

- **Novo recurso visual**: implementado para `diagnostics: request payload size
  breakdown` como metadata sanitizado do turno, persistido em
  `Message.payload_diagnostics`, retornado pelo endpoint de histórico e
  renderizado no chat com resumo compacto e detalhes expansíveis.
- **Patches locais do OpenClaude**: `grep-tool-n-alias.patch`,
  `auto-approve-tools.patch`, `multimodal-proto.patch`,
  `multimodal-grpc-handler.patch` e `read-empty-pages.patch` aplicam limpo no
  commit `66ed9b61dcefea4bd58d1c24011cf32015b0fb29`. Os antigos patches
  `mcp-grpc-integration.patch`, `worktree-tool-guard.patch`,
  `numeric-parameter-grep-guard.patch` e
  `numeric-parameter-grep-wrapper.patch` foram absorvidos no patch gRPC
  consolidado porque seus hunks falhavam na v0.14.0.
- **Sem novo visual**: provider auth, xAI/Grok OAuth, OAuth callback hardening,
  UTF-8 input, retry 402, stdin/MCP freeze guard, TaskListV2, Read.pages e XML
  permanecem fora do chat CappyCloud; falhas finais continuam usando o fluxo de
  erro existente.
- **Validação de visual existente**: timeout, stdout de tool com erro,
  action-required, thinking/resume, Agent tool e loops repetidos de falha foram
  cobertos por testes de stream/agent runtime e por cenários manuais no
  quickstart.

### Functional Requirements

- **FR-001**: System MUST update the agent runtime target to OpenClaude v0.14.0 and keep the selected upstream revision traceable.
- **FR-002**: System MUST classify every v0.14.0 feature and bug fix as one of: new chat visual, validation of existing chat visual, or no chat visual impact.
- **FR-003**: Users MUST be able to view a safe request payload size breakdown in the chat when the agent provides that diagnostic data.
- **FR-004**: System MUST show payload size diagnostics as secondary context for the relevant turn, not as the main assistant answer.
- **FR-004a**: System MUST persist payload size diagnostics with the relevant chat turn so the same breakdown is available after reloading the conversation.
- **FR-004b**: System MUST display payload diagnostics as a compact summary by default, with detailed breakdown content collapsed but expandable.
- **FR-004c**: System MUST include total payload size and the three largest safe categories in the compact summary, while the expanded view shows all safe categories available for the turn.
- **FR-005**: System MUST avoid exposing secrets, raw provider keys, full hidden prompts, or raw binary attachment data in any payload breakdown.
- **FR-006**: System MUST preserve existing chat treatments for tool execution, tool errors, action-required prompts, session progress, timeouts, usage, and cost.
- **FR-007**: System MUST make timeout and provider failure states visible enough that users do not remain on an infinite spinner.
- **FR-008**: System MUST keep provider authentication and OAuth changes out of the chat unless they produce an actionable user-facing failure for the current turn.
- **FR-009**: System MUST support conversations where the diagnostic data is missing, partial, or not supported by the selected provider.
- **FR-010**: System MUST provide a reviewable acceptance checklist so the team can verify the visual scope before implementation.

### Key Entities *(include if feature involves data)*

- **Release Item**: One feature or bug fix from OpenClaude v0.14.0, with title, category, source reference, and visual scope decision.
- **Chat Visual Treatment**: The user-facing treatment assigned to a release item: new diagnostic UI, existing state validation, or no chat UI change.
- **Payload Size Breakdown**: Safe summary of request size by category, such as user message, attachments, repository context, tool/native results, and system/runtime context; compact display includes the total and three largest safe categories.
- **Agent Turn**: One user request and the resulting agent activity, answer, persisted diagnostics, usage, and terminal state.

### Runtime Context, Security & Evidence *(mandatory when applicable)*

- **RC-001**: The selected runtime is OpenClaude v0.14.0. External tag check on 2026-06-17 returned `refs/tags/v0.14.0` at `66ed9b61dcefea4bd58d1c24011cf32015b0fb29`.
- **RC-002**: Chat-visible diagnostics must be sanitized because the agent runtime receives repository context, attachments, provider configuration, and tool outputs.
- **RC-003**: Repository evidence reviewed: architecture describes OpenClaude running inside the sandbox and communicating with the chat pipeline; the current chat stream exposes text, tool, action, status, done, and error events; the current UI renders session progress, tool activity, action-required prompts, usage, and cost.
- **RC-004**: Sandbox image behavior is in scope because the runtime version is pinned during sandbox build. Automatic production deployment, image push, or container rollout is out of scope for this specification.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of listed v0.14.0 release items have a documented chat visual decision before planning starts.
- **SC-002**: In a diagnostic-enabled turn, a user can identify the largest payload category in under 10 seconds without reading logs.
- **SC-003**: In turns without diagnostic data, the chat UI remains visually unchanged and produces no empty diagnostic container in 100% of tested cases.
- **SC-004**: Timeout, tool error, action-required, resume, and normal completion scenarios each have at least one acceptance test or manual verification scenario before implementation is considered complete.
- **SC-005**: No displayed payload diagnostic includes raw secrets, provider API keys, hidden prompts, or binary attachment content in security review.
- **SC-006**: In 100% of tested diagnostic-enabled turns, reloading the conversation preserves the same safe payload breakdown for that turn.

## Assumptions

- The requested scope is the CappyCloud chat UI, not the OpenClaude terminal UI or admin provider setup screens.
- The diagnostics payload breakdown from OpenClaude v0.14.0 can be surfaced through the agent event flow or derived from safe runtime metadata during planning.
- Existing chat visual treatments remain the preferred default unless a release item introduces information users could not previously see.
- Provider setup for xAI/Grok may be handled separately if the product decides to expose first-class provider onboarding outside the chat.
