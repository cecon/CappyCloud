# Feature Specification: Project-Aware Chat Suggestions

**Feature Branch**: `[009-project-chat-suggestions]`

**Created**: 2026-07-22

**Status**: Draft

**Input**: User description: "quero implementar isso na tela inicial do chat, basicamente o sistema olha para o projeto escolhido e sugere coisas para ele se mudar o projeto muda a descricao, assim nao fica algo inutil e repetitivo, sugiro tambem olhar o que todo mundo pergunta nesses projetos e criar uma tabela para ter esses 4 ou 3 cards de sugestao bem mais especificos e adaptados, a cada x periodo de tempo devemos rodar algo para analizar e recalibrar"

## Clarifications

### Session 2026-07-22

- Q: Como as sugestoes recalibradas devem virar cards visiveis para os usuarios? -> A: Publicar automaticamente sugestoes que passem filtros de seguranca e diversidade; sinais de volume e frequencia melhoram a prioridade ao longo do tempo, e administradores podem suprimir depois.
- Q: Qual deve ser o volume minimo para uma sugestao gerada automaticamente poder aparecer? -> A: As sugestoes iniciais aparecem desde o primeiro momento com base no contexto do projeto; o historico de perguntas melhora e recalibra os cards depois.
- Q: Quais fontes podem alimentar as sugestoes iniciais antes de existir historico de perguntas? -> A: Metadados do projeto mais documentos e skills ja cadastrados ou ingeridos para aquele projeto.
- Q: Qual cadencia de recalibracao devemos assumir na especificacao? -> A: Recalibrar diariamente e tambem quando documentos ou skills do projeto mudarem.
- Q: Qual escopo de historico pode alimentar a recalibracao das sugestoes? -> A: Historico agregado e anonimizado de todos os usuarios autorizados daquele projeto.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Ver sugestoes especificas do projeto selecionado (Priority: P1)

Como pessoa iniciando uma conversa, quero que a tela inicial do chat mostre perguntas e tarefas sugeridas para o projeto selecionado, para comecar com prompts uteis em vez de cards genericos repetidos.

**Why this priority**: O valor principal do pedido e substituir os cards genericos da tela inicial por sugestoes que mudam conforme o projeto. Sem isso, a experiencia continua parecendo decorativa e pouco acionavel.

**Independent Test**: Pode ser testado abrindo a tela inicial do chat, selecionando um projeto com sugestoes disponiveis e confirmando que o titulo, a descricao e os cards ficam relacionados ao projeto escolhido.

**Acceptance Scenarios**:

1. **Given** a tela inicial do chat sem mensagens e um projeto selecionado, **When** existem sugestoes validas para esse projeto, **Then** a tela mostra de 3 a 4 cards com textos especificos para o projeto selecionado.
2. **Given** a tela inicial mostra sugestoes de um projeto, **When** o usuario troca para outro projeto, **Then** o titulo contextual, a descricao e os cards mudam para refletir o novo projeto sem exigir recarregar a pagina.
3. **Given** o usuario clica em um card sugerido, **When** o card e aplicado, **Then** o texto sugerido preenche o composer preservando anexos, branch, modelo e modo de permissao ja selecionados.
4. **Given** o projeto selecionado ainda nao possui historico de perguntas suficiente, **When** a tela inicial e exibida, **Then** o usuario ve sugestoes iniciais baseadas em metadados, documentos e skills cadastrados ou ingeridos para aquele projeto, nao textos fixos indistinguiveis para todos os projetos.

---

### User Story 2 - Aprender com perguntas reais do projeto (Priority: P2)

Como pessoa responsavel pela qualidade do produto, quero que as sugestoes sejam recalibradas a partir dos tipos de perguntas feitas nos projetos, para que os cards acompanhem duvidas, rotinas e problemas recorrentes do uso real.

**Why this priority**: O usuario pediu explicitamente olhar "o que todo mundo pergunta nesses projetos" e manter uma tabela de sugestoes mais adaptadas. Isso evita que a melhoria envelheca depois do primeiro cadastro manual.

**Independent Test**: Pode ser testado registrando conversas de exemplo em um projeto, executando o ciclo de analise e confirmando que sugestoes agregadas e seguras aparecem como candidatas ou sugestoes ativas para aquele projeto.

**Acceptance Scenarios**:

1. **Given** um projeto com mensagens recentes disponiveis, **When** a analise periodica roda, **Then** o sistema identifica temas recorrentes sem expor textos pessoais ou dados sensiveis de uma conversa individual.
2. **Given** a analise produz novas sugestoes que passam diversidade e filtros de seguranca, **When** elas sao salvas, **Then** cada sugestao elegivel pode melhorar automaticamente os cards do projeto correto e registra origem, periodo analisado e momento da ultima recalibracao.
3. **Given** perguntas recorrentes mudam ao longo do tempo, **When** o ciclo diario de recalibracao roda novamente, **Then** sugestoes antigas perdem prioridade ou sao substituidas por sugestoes mais relevantes.
4. **Given** documentos ou skills de um projeto sao cadastrados, atualizados ou reingeridos, **When** a mudanca fica disponivel para o produto, **Then** as sugestoes desse projeto entram em recalibracao sem esperar apenas o proximo ciclo diario.
5. **Given** um projeto tem perguntas de varios usuarios autorizados, **When** a recalibracao usa esse historico, **Then** apenas temas agregados e anonimizados influenciam as sugestoes, sem revelar autores ou conversas individuais.
6. **Given** um usuario tem acesso apenas a alguns projetos, **When** abre o chat, **Then** recebe apenas sugestoes de projetos que ele pode acessar.

---

### User Story 3 - Controlar qualidade e frescor das sugestoes (Priority: P3)

Como administrador ou mantenedor do CappyCloud, quero acompanhar quando cada projeto foi analisado e se as sugestoes estao saudaveis, para corrigir conteudo ruim, vazio, inseguro ou desatualizado.

**Why this priority**: A recalibracao automatica precisa de transparencia operacional para nao gerar prompts ruins, duplicados ou vazando contexto de usuarios.

**Independent Test**: Pode ser testado consultando o estado de sugestoes de um projeto apos uma analise bem-sucedida, uma analise sem dados suficientes e uma analise com falha.

**Acceptance Scenarios**:

1. **Given** um projeto possui sugestoes ativas, **When** um mantenedor consulta o estado delas, **Then** consegue ver quantidade, data da ultima analise, validade, status e motivo de fallback quando aplicavel.
2. **Given** a analise nao encontra dados suficientes, **When** a tela inicial e aberta, **Then** o usuario ve sugestoes fallback uteis e o estado operacional registra que a calibracao ainda e insuficiente.
3. **Given** uma sugestao e marcada como insegura, duplicada ou ruim, **When** ela seria exibida, **Then** o sistema deixa de mostra-la e usa a proxima sugestao valida ou fallback.

### Edge Cases

- O usuario ainda nao selecionou projeto; a tela deve pedir selecao de projeto e pode mostrar cards neutros apenas como fallback temporario.
- O projeto selecionado muda rapidamente enquanto sugestoes estao carregando; a tela deve renderizar apenas sugestoes do projeto atualmente selecionado.
- O projeto tem menos de 3 sugestoes recalibradas pelo historico; a tela deve completar ate 3 cards com sugestoes iniciais do contexto do projeto, sem cards vazios.
- O projeto tem muitas sugestoes validas; a tela deve escolher no maximo 4, priorizando relevancia, frescor e diversidade.
- Varias pessoas perguntaram coisas parecidas com palavras diferentes; a analise deve agrupar temas sem criar cards duplicados.
- Mensagens contem dados sensiveis, segredos, nomes de clientes ou incidentes especificos; sugestoes devem generalizar o tema e nao reproduzir detalhes privados.
- Uma pergunta vem de usuario que perdeu acesso ao projeto depois; o historico pode contribuir apenas como sinal agregado e anonimizado, mas nunca como conteudo individual visivel.
- Um projeto foi removido, desativado ou o usuario perdeu acesso; sugestoes desse projeto nao devem aparecer.
- A analise periodica falha; sugestoes existentes continuam disponiveis ate expirarem ou ate o fallback assumir.
- Documentos ou skills do projeto ainda nao foram cadastrados ou ingeridos; as sugestoes iniciais devem usar apenas os metadados disponiveis do projeto.
- Documentos ou skills sao atualizados varias vezes no mesmo dia; recalibracoes redundantes devem ser agrupadas ou limitadas para evitar trabalho repetido.
- O sandbox do projeto ainda nao esta pronto; a tela inicial nao deve depender de analise em tempo real do conteudo do repositorio para exibir sugestoes.
- A tela esta em uma conversa existente com historico; sugestoes iniciais nao devem disputar espaco com mensagens ja enviadas.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST show project-aware initial chat suggestions when the chat has no messages and a project is selected.
- **FR-002**: System MUST display between 3 and 4 suggestion cards when enough valid suggestions exist for the selected project.
- **FR-003**: System MUST update the initial chat heading, supporting description and suggestion cards when the selected project changes.
- **FR-004**: Users MUST be able to click a suggestion card to populate the chat composer with the suggested prompt.
- **FR-005**: Selecting a suggestion MUST preserve the selected project, branch, sandbox, model, permission mode and any attachments already prepared by the user.
- **FR-006**: System MUST provide useful initial suggestions from project context as soon as a project is selected, even before the project has enough question history.
- **FR-007**: Initial project-context suggestions MUST use available project metadata plus documents and skills already registered or ingested for that project, instead of identical global copy for every project.
- **FR-008**: System MUST collect aggregate and anonymized usage signals from questions by users authorized for each project for the purpose of suggestion calibration.
- **FR-009**: System MUST NOT expose raw user messages, private conversation content, secrets, customer identifiers or sensitive incident details in generated suggestions.
- **FR-010**: System MUST store curated or generated project suggestions with project association, title, prompt text, category, priority, status, source, last analysis period and last recalibration timestamp.
- **FR-011**: System MUST retain enough analysis metadata for maintainers to know whether suggestions are calibrated, fallback-based, stale, disabled or failed.
- **FR-012**: System MUST support a daily recalibration process that analyzes recent project question patterns.
- **FR-013**: The recalibration process MUST prioritize relevance, recency, frequency and diversity so the final cards do not all represent the same theme.
- **FR-014**: The recalibration process MUST degrade gracefully when message history is sparse, project context is unavailable or analysis fails.
- **FR-015**: System MUST ensure users only see suggestions for projects they are authorized to access.
- **FR-016**: System MUST support disabling or suppressing individual suggestions that are unsafe, low quality, duplicated or no longer relevant.
- **FR-017**: Suggestion text MUST be written in user-facing Portuguese by default.
- **FR-018**: Suggestion cards MUST remain concise enough to fit in the existing initial chat layout on desktop and mobile without overlapping surrounding controls.
- **FR-019**: System MUST avoid showing project-specific suggestions in conversations that already have visible message history, unless a later feature explicitly adds in-conversation suggestions.
- **FR-020**: System MUST make stale or failed calibration observable to maintainers without interrupting normal chat usage.
- **FR-021**: System MUST publish initial project-context suggestions immediately when they pass safety filters, and MUST let question-history recalibration improve or replace them over time when enough signal exists.
- **FR-022**: Administrators MUST be able to suppress automatically published suggestions after publication without disabling the whole project suggestion feature.
- **FR-023**: Initial suggestion display MUST NOT depend on real-time repository code analysis or sandbox readiness.
- **FR-024**: System MUST trigger or schedule recalibration for a project when that project's registered or ingested documents or skills change.
- **FR-025**: System MUST avoid excessive duplicate recalibration work when multiple document or skill changes happen close together.
- **FR-026**: System MUST NOT expose authors, individual conversations or raw prompts when using cross-user project history for recalibration.

### Key Entities *(include if feature involves data)*

- **Project Suggestion**: A prompt suggestion associated with one project, including card title, prompt text, category, priority, status, source and freshness metadata.
- **Suggestion Calibration Run**: One analysis cycle for a project or group of projects, including analysis period, status, number of eligible messages, number of suggestions produced and failure reason when applicable.
- **Project Question Pattern**: An aggregated and anonymized theme derived from questions by users authorized for a project.
- **Initial Suggestion Profile**: Project-aware prompts derived from project metadata plus documents and skills already registered or ingested before calibrated question-history suggestions are available.
- **Suggestion Visibility Context**: The selected project, user access, chat empty-state status, selected branch, sandbox and composer state used to decide what cards may appear.

### Runtime Context, Security & Evidence *(mandatory when applicable)*

- **RC-001**: Repository evidence reviewed: `web/src/pages/ChatPage.tsx` lines 2220-2264 render the current initial chat welcome panel and four static quick-action cards.
- **RC-002**: Repository evidence reviewed: `web/src/pages/ChatPage.tsx` lines 2381-2417 render the project selector used by the initial chat state.
- **RC-003**: Repository evidence reviewed: `services/api/app/domain/entities.py` lines 210-220 model conversations with selected repositories and permission mode.
- **RC-004**: Repository evidence reviewed: `services/api/app/domain/entities.py` lines 252-262 model messages with content, usage and cost metadata that can inform aggregate analysis.
- **RC-005**: Repository evidence reviewed: `services/api/app/infrastructure/orm_models_platform.py` lines 109-134 model repositories with slug, name, clone URL, Confluence settings, sandbox status and active state.
- **RC-006**: Repository evidence reviewed: `docs/ARCHITECTURE.md` states business logic belongs in application use cases and selected repository/runtime context is conversation behavior.
- **RC-007**: Security rule: suggestion generation and display must respect repository authorization, cross-user privacy, project visibility, secret redaction and existing chat permission controls.
- **RC-008**: Operational rule: recalibration may be scheduled or manually triggered in later implementation artifacts, but production deployment, external documentation crawling and administrative review tooling are out of scope unless planned explicitly.
- **RC-009**: Initial suggestion sources are limited to project metadata and already registered or ingested documents/skills; real-time repository analysis is out of scope for the initial empty-state card display.
- **RC-010**: Recalibration cadence is daily, with additional recalibration triggered or scheduled after project document or skill changes.
- **RC-011**: Question-history recalibration may use cross-user project history only as aggregate anonymized signals from users authorized for that project; raw prompts, authors and individual conversation traces must not be shown in suggestions.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For projects with at least 3 active safe suggestions, users see project-specific cards within 2 seconds of selecting the project in 95% of normal development smoke checks.
- **SC-002**: When switching between two projects with different suggestions, 100% of validation attempts update the visible cards and contextual copy to the newly selected project.
- **SC-003**: Clicking a suggestion fills the composer with the intended prompt and preserves selected project, branch, sandbox, model, permission mode and attachments in 100% of validation scenarios.
- **SC-004**: For projects without calibrated question-history suggestions, users still see at least 3 project-aware initial prompts in 100% of validation scenarios where project metadata is available.
- **SC-005**: Recalibration runs produce at most 4 active suggestions per project for display and retain metadata showing period, status and freshness for 100% of analyzed projects.
- **SC-006**: No validation sample suggestion contains raw secrets, private conversation snippets, customer identifiers or unsupported project details.
- **SC-007**: Unauthorized users are blocked from seeing suggestions for inaccessible projects in 100% of negative access tests.
- **SC-008**: At least 80% of users in a guided review rate the new cards as more useful than the current generic quick actions.
- **SC-009**: Automatically published suggestions pass safety checks in 100% of publication validation scenarios, and question-history suggestions pass diversity checks before replacing initial project-context cards.
- **SC-010**: Projects with active data changes are recalibrated by the next daily cycle or by the document/skill change trigger in 100% of operational validation scenarios.
- **SC-011**: Cross-user history validation confirms that 100% of generated suggestions are based on aggregate anonymized themes and do not reveal authors or individual conversation text.

## Assumptions

- The first version targets the empty initial chat state shown before the first message, not suggestions during an active conversation.
- The product should show 4 cards when possible, but 3 cards is acceptable when fewer safe, high-quality suggestions exist.
- Portuguese remains the default language for visible suggestions and explanatory text.
- "Projeto" maps to the selected repository/workspace in the current chat UI.
- Historical question analysis should use aggregate anonymized themes from users authorized for the project, not direct reuse of individual user prompts, and should improve suggestions after the initial project-context cards are already available.
- Initial suggestions should use only data already known to CappyCloud for the selected project, so selecting a project does not need to wait for sandbox code inspection.
- The default recalibration cadence is daily, with additional recalibration after document or skill changes; planning may decide the exact execution window and debounce behavior.
- Manual curation or suppression by maintainers is allowed, but a full editorial management screen is not required for the first release unless the plan decides otherwise.
