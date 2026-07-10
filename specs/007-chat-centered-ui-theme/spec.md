# Feature Specification: Chat-Centered UI Theme

**Feature Branch**: `[007-chat-centered-ui-theme]`

**Created**: 2026-07-08

**Status**: Draft

**Input**: User description: "Na pasta tmp temos um theme novo com telas e UX que devem ser implementadas, usando o shadcn e twen, e deve ser criado um tema para todos os componentes serem tematizados. Todas as telas seguem a nova ideia de o chat ser o centro do layout e os demais menus foram para o menu do usuario."

## Clarifications

### Session 2026-07-08

- Q: Qual deve ser o escopo da migracao visual no primeiro release?-> A: Migrar todas as telas autenticadas existentes no primeiro release.
- Q: Qual deve ser a base do design system no primeiro release?-> A: Substituir o frontend autenticado por shadcn/ui e Tailwind no primeiro release.
- Q: Como deve ficar a navegacao lateral no chat?-> A: Seguir o template de `tmp/Cappy`, mantendo os apoios laterais previstos nele e removendo a duplicidade atual dos dois menus laterais no chat.
- Q: Como as areas administrativas devem abrir no novo layout?-> A: Administracao abre como console, modal ou painel sobre a experiencia do chat, conforme `tmp/Cappy`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Conversar Como Experiencia Central (Priority: P1)

Como usuario autenticado, quero que a tela principal coloque o chat no centro da experiencia, com contexto essencial visivel e apenas os apoios laterais previstos no template de referencia, para iniciar, acompanhar e concluir interacoes com o agente com menos distracao.

**Why this priority**: O chat e o fluxo principal do produto. Se essa experiencia nao estiver clara e prioritaria, as demais areas da interface continuam fragmentadas.

**Independent Test**: Pode ser testado abrindo a aplicacao autenticada, iniciando uma conversa e validando que o chat, o historico relevante, o compositor, o contexto de workspace/repositorio/modelo e os pedidos de permissao estao disponiveis sem navegar para outra tela e sem a duplicidade atual de dois menus laterais no chat.

**Acceptance Scenarios**:

1. **Given** um usuario autenticado sem conversa ativa, **When** ele acessa o produto, **Then** a interface apresenta uma entrada clara para nova conversa com o chat como area principal.
2. **Given** uma conversa em andamento, **When** o agente responde, pede permissao ou exibe atividade, **Then** esses eventos aparecem dentro do fluxo conversacional sem esconder o compositor.
3. **Given** uma conversa com historico, **When** o usuario seleciona uma conversa anterior, **Then** o conteudo do chat ocupa a area central e mantem contexto visual de workspace, repositorio, sandbox e modelo selecionado.

---

### User Story 2 - Acessar Funcoes Secundarias Pelo Menu Do Usuario (Priority: P2)

Como usuario, quero encontrar configuracoes, administracao, acessos, tema e funcoes secundarias no menu do usuario, para que a navegacao cotidiana fique concentrada na conversa e nao em menus laterais dispersos.

**Why this priority**: A mudanca de arquitetura visual depende de remover competicao entre menus e chat, mantendo as funcoes importantes acessiveis.

**Independent Test**: Pode ser testado abrindo o menu do usuario e validando que funcoes administrativas e de configuracao antes expostas em menus principais continuam acessiveis conforme o perfil do usuario.

**Acceptance Scenarios**:

1. **Given** um usuario comum, **When** ele abre o menu do usuario, **Then** ve apenas as opcoes permitidas para sua conta, incluindo preferencias de tema quando disponiveis.
2. **Given** um administrador, **When** ele abre o menu do usuario, **Then** ve atalhos para gestao do workspace, usuarios, acessos, repositorios, sandboxes, skills, MCPs e modelos quando tiver permissao.
3. **Given** um usuario sem permissao administrativa, **When** ele procura opcoes de administracao, **Then** essas opcoes nao aparecem e nenhuma rota restrita fica acessivel pela interface.

---

### User Story 3 - Aplicar Tema Unificado Em Todas As Telas (Priority: P2)

Como usuario, quero que todas as telas, modais, menus, cards, tabelas, formularios e estados interativos usem o mesmo tema visual, para sentir que o produto e consistente e confiavel.

**Why this priority**: O novo visual so entrega valor se for sistemico. Telas misturando estilos antigos e novos reduzem confianca e dificultam demonstracoes.

**Independent Test**: Pode ser testado percorrendo as telas autenticadas, alternando entre temas claro e escuro quando disponivel, e verificando consistencia de cores, espacamentos, estados de hover, foco, erro, vazio e carregamento.

**Acceptance Scenarios**:

1. **Given** qualquer tela autenticada, **When** o usuario alterna o tema visual, **Then** componentes de navegacao, chat, formularios, listas, modais e paineis refletem a mudanca sem contraste inadequado.
2. **Given** uma acao que abre modal ou painel, **When** o componente aparece, **Then** ele usa a mesma linguagem visual do restante da aplicacao.
3. **Given** uma tela com dados administrativos, **When** o usuario filtra, edita ou salva informacoes, **Then** estados de sucesso, erro, carregamento e vazio seguem o tema unificado.

---

### User Story 4 - Preservar Gestao Administrativa No Novo Layout (Priority: P3)

Como administrador, quero continuar gerenciando usuarios, repositorios, sandboxes, MCPs, skills, provedores e modelos em um console, modal ou painel sobre a experiencia do chat, para nao perder capacidade operacional durante a modernizacao.

**Why this priority**: A administracao e essencial, mas deve se adaptar ao novo layout centrado no chat depois que a experiencia principal estiver resolvida.

**Independent Test**: Pode ser testado acessando cada area administrativa a partir do menu do usuario, confirmando que ela abre sobre a experiencia do chat conforme `tmp/Cappy`, e executando pelo menos uma acao de leitura e uma acao de alteracao permitida em cada cadastro critico.

**Acceptance Scenarios**:

1. **Given** um administrador, **When** ele acessa a gestao de usuarios, **Then** consegue visualizar papeis, status e permissoes com a nova linguagem visual.
2. **Given** um administrador, **When** ele acessa provedores, MCPs, skills ou modelos, **Then** consegue identificar estado ativo, conectividade, disponibilidade e acoes permitidas.
3. **Given** uma acao administrativa sensivel, **When** o usuario confirma ou cancela, **Then** a interface comunica impacto e resultado de forma clara.

### Edge Cases

- Quando o usuario acessa uma tela antiga ou pouco usada, ela deve usar o tema unificado ou apontar claramente indisponibilidade planejada, sem quebrar a navegacao.
- Quando o menu do usuario concentra muitas opcoes administrativas, ele deve manter agrupamento, busca ou hierarquia suficiente para nao esconder funcoes criticas.
- Quando o chat recebe mensagens longas, blocos de codigo, pedidos de permissao ou atividade do agente, o compositor deve continuar acessivel e a leitura nao deve exigir rolagem horizontal.
- Quando o tema muda entre claro e escuro, textos, icones, bordas, badges e estados selecionados devem manter contraste adequado.
- Quando o usuario nao tem permissao para uma funcao migrada para o menu do usuario, a opcao deve ficar oculta ou bloqueada com mensagem compreensivel.
- Quando capturas ou referencias de `tmp/Cappy` divergirem do comportamento real existente, o produto deve preservar autorizacao, dados e fluxos ja suportados pelo CappyCloud.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST make the authenticated chat experience the primary layout surface for regular product use.
- **FR-002**: The system MUST provide a clear new conversation entry point from the primary chat layout.
- **FR-003**: The system MUST keep conversation history and chat support rails discoverable according to the `tmp/Cappy` reference, without preserving the current duplicated two-sidebar chat layout.
- **FR-004**: The system MUST show active workspace, selected repository or context, sandbox state, permission mode and selected model in a concise context area during chat usage.
- **FR-005**: The system MUST display agent activity, permission requests, confirmations and actionable results as part of the conversation flow.
- **FR-006**: Users MUST be able to access secondary navigation, account actions, preferences and allowed administrative areas from the user menu.
- **FR-007**: The system MUST hide or block user-menu actions that the current user is not authorized to perform.
- **FR-008**: The system MUST define a unified visual theme that applies to shared components across chat, navigation, menus, modals, forms, tables, cards, badges and administrative panels.
- **FR-009**: The system MUST support dark and light visual modes when theme switching is available in the user experience.
- **FR-010**: The system MUST preserve readable contrast, visible focus, hover, selected, disabled, loading, empty, success and error states across themed components.
- **FR-011**: The system MUST use the new `tmp/Cappy` references as the visual and state reference for chat, new conversation, sandbox/access views, user management, permissions, MCP/server management, skills, providers and model catalog views where those areas exist in the product.
- **FR-012**: The system MUST keep administrative workflows available to authorized administrators after the navigation changes.
- **FR-013**: The system MUST preserve existing security boundaries for user roles, repository visibility, sandbox access, model availability and administrative actions.
- **FR-014**: The system MUST keep user-facing text in accessible Portuguese for the product surfaces covered by this redesign.
- **FR-015**: The system MUST provide responsive behavior for common desktop and notebook viewport sizes used in demonstrations, without overlapping text, controls or chat content.
- **FR-016**: The system MUST ensure long chat messages, code blocks, activity panels and permission cards remain readable without forcing horizontal page scrolling.
- **FR-017**: The system MUST expose enough visual states for demos to show normal chat, new chat, permission request, admin modal/panel, user access details and model/provider status.
- **FR-018**: The system MUST migrate all existing authenticated screens into the first redesign release, with no authenticated screen intentionally left in the previous visual language.
- **FR-019**: The redesigned authenticated frontend MUST use shadcn/ui and Tailwind as the component and theming foundation for the first release.
- **FR-020**: Administrative areas MUST open as a console, modal or panel layered over the chat-centered experience, following the `tmp/Cappy` reference instead of replacing the primary experience with unrelated full-page navigation.

### Key Entities *(include if feature involves data)*

- **Theme**: Visual language applied to the product, including color modes, surfaces, text hierarchy, borders, spacing, component states and brand assets.
- **User Menu**: Account-centered navigation surface that exposes preferences, account actions and role-appropriate secondary workflows.
- **Chat Layout**: Primary authenticated workspace centered on conversation, composer, context indicators, agent activity and permission/result cards.
- **Administrative Area**: Authorized management surface for workspace operations such as users, accesses, repositories, sandboxes, MCP servers, skills, providers and models.
- **Design Reference**: Temporary local reference package under `tmp/Cappy` containing HTML, brand assets and screenshots used to guide the desired UX direction.

### Runtime Context, Security & Evidence *(mandatory when applicable)*

- **RC-001**: The feature is based on repository-local evidence: `tmp/Cappy/CappyCloud.dc.html`, screenshots under `tmp/Cappy/screenshots/`, project architecture in `docs/ARCHITECTURE.md`, development gates in `docs/AGENT_RULES.md`, and the Spec Kit constitution in `.specify/memory/constitution.md`.
- **RC-002**: Authorization rules for administrators, users, repository access, sandbox access, model access and closed routes must remain enforced by existing product permissions, not only by visible menu choices.
- **RC-003**: No external documentation evidence is required for this specification; if planning introduces external UI library documentation, it must cite real returned sources at that phase.
- **RC-004**: This feature changes frontend experience and design system behavior only; it must not change sandbox, Git, container or network behavior unless a later plan explicitly scopes that work.
- **RC-005**: Planning must explicitly use the project constitution path for approved design-system migrations when adopting the requested shadcn/ui and Tailwind foundation.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In a product demo, a user can start a new conversation, choose or confirm context, send a message and see the first agent response path in under 60 seconds.
- **SC-002**: 100% of existing authenticated screens use the unified theme for primary controls, text, surfaces and interaction states in the first release.
- **SC-003**: 100% of user-menu options shown to a non-admin user are permitted for that user profile.
- **SC-004**: 100% of administrative entry points available before the redesign remain reachable to authorized administrators in the redesigned experience.
- **SC-004a**: 100% of redesigned administrative entry points open in the console, modal or panel pattern defined by the `tmp/Cappy` reference.
- **SC-005**: In reviewed desktop and notebook viewport sizes, no critical chat, menu, modal or administrative control overlaps another control or requires horizontal page scrolling.
- **SC-006**: Users evaluating the redesign can identify the chat as the main product surface within 5 seconds of opening the authenticated app.
- **SC-007**: Theme review confirms readable contrast for primary text, secondary text, buttons, selected states, error states and focus states in both supported visual modes.

## Assumptions

- The first release targets the authenticated web application, not public marketing pages.
- Login and change-password are public-adjacent/account surfaces and may be visually aligned to avoid clashing with the authenticated redesign, but marketing pages remain out of scope.
- The local `tmp/Cappy` package is the design and UX reference for the desired direction, but product behavior remains governed by existing CappyCloud authorization and runtime rules.
- The phrase "twen" is treated as a reference to Tailwind.
- The user-requested component library and theme implementation choice is shadcn/ui with Tailwind for the authenticated frontend redesign; planning must account for the governed migration path from the current Mantine-based frontend.
- Mobile-specific redesign is not the primary target for the first release unless planning expands scope, but all existing authenticated desktop/notebook screens are in scope.
- Existing backend contracts should be reused where possible; this feature should not require new business capabilities unless a screen cannot function with current data.
