# Feature Specification: Frontend do CappyCloud no C3Theme

**Feature Branch**: `013-c3theme-frontend`

**Created**: 2026-10-13

**Status**: Draft

**Input**: O dono do produto quer o CappyCloud no C3Theme (`cecon/C3Theme`, tema
React + MUI derivado do Able Pro, com pacote `@c3theme/ui`, `seed` e `demo`).
Recomendou "trazer o seed e vir trazendo as funcionalidades": começar pelo
esqueleto do seed e portar as telas uma a uma.

## Contexto

- O frontend atual (`web/`) usa Tailwind 4, Radix e CSS modules: 107
  componentes, 29 arquivos de estilo, 19 telas e 5 redirecionamentos (chat,
  configurações, skills, runs, MCP, analytics e 11 telas de administração).
- O C3Theme usa outro sistema de componentes. A migração reescreve a camada
  visual de cada tela; a lógica de acesso à API, hooks e validações pode ser
  reaproveitada.
- A constituição (princípio VI) permite trocar o sistema de design só com spec,
  plano e tarefas que aprovem a troca, atualizem as skills de frontend, cubram
  todas as telas e definam o fim da convivência entre os dois sistemas.

## Clarifications

### Session 2026-10-13

- Q: Como trazer o tema sem publicar o código do Able Pro (o repositório do
  CappyCloud é público)? → A: O dono do produto é dono do C3Theme. O tema
  continua só no repositório privado e o CappyCloud o consome como dependência
  privada; nenhum arquivo do tema entra no repositório público.
- Q: Onde nasce o frontend novo durante a migração? → A: App novo ao lado do
  atual; o atual segue no ar até o novo cobrir todas as telas.
- Q: A licença do Able Pro cobre o CappyCloud? → A: Sim, confirmado pelo dono
  do produto.
- Q: O seed tem arte e telas de demonstração do Able Pro; como trazê-lo para o
  repositório público? → A: Seed como referência: o frontend novo segue a
  estrutura do seed, mas só com código do CappyCloud, sem as ilustrações,
  avatares e widgets de demonstração. Componente que faltar vai para o pacote
  privado do tema.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Entrar no CappyCloud com a cara do C3 (Priority: P1)

O usuário abre o frontend novo, entra com o mesmo e-mail e senha que já usa,
troca a senha quando o sistema exigir e cai num layout C3: menu lateral, cabeçalho,
tema claro/escuro e textos em português, com o nome e a marca do CappyCloud.

**Why this priority**: É o esqueleto do seed ligado ao backend real. Sem ele
nenhuma tela pode ser portada, e já permite validar o tema com usuários.

**Independent Test**: Com o frontend novo publicado, entrar com uma conta
existente, ver o layout e o menu, alternar tema, sair e entrar de novo.

**Acceptance Scenarios**:

1. **Given** uma conta ativa, **When** o usuário entra no frontend novo com e-mail
   e senha, **Then** vê o layout C3 com seu e-mail e papel no rodapé do menu.
2. **Given** uma conta marcada para trocar a senha, **When** ela entra, **Then** é
   levada à troca de senha antes de qualquer outra tela.
3. **Given** um usuário sem papel de administrador, **When** abre o menu, **Then**
   não vê os itens de administração e não acessa essas rotas pelo endereço.
4. **Given** credenciais erradas, **When** tenta entrar, **Then** vê a mensagem de
   erro em português sem perder o que digitou.

---

### User Story 2 - Conversar com o agente no frontend novo (Priority: P2)

O usuário usa o chat inteiro no frontend novo: lista e busca de conversas, nova
conversa, escolha de workspace/repositório e modelo, resposta em tempo real com
os passos e ferramentas do agente, perguntas de permissão, anexos, diff, uso e
custo.

**Why this priority**: É a tela que todos usam todos os dias. Com ela portada, a
maior parte dos usuários pode trabalhar só no frontend novo.

**Independent Test**: Fazer uma pergunta técnica num workspace, acompanhar os
passos, responder um pedido de permissão e conferir custo e histórico.

**Acceptance Scenarios**:

1. **Given** um workspace autorizado, **When** o usuário envia uma pergunta,
   **Then** a resposta aparece em tempo real com os passos e o custo no fim.
2. **Given** o agente pedindo permissão ou fazendo uma pergunta, **When** o
   usuário responde, **Then** o turno continua com a resposta dele.
3. **Given** uma conversa antiga, **When** o usuário a abre, **Then** vê o mesmo
   histórico, passos e custos que via no frontend atual.

---

### User Story 3 - Telas do usuário (Priority: P3)

Skills, runs, servidores MCP, analytics e configurações (só super admin) funcionam no frontend
novo com o mesmo comportamento do atual.

**Why this priority**: Completa a experiência de quem não é administrador.

**Independent Test**: Para cada tela, executar o checklist de paridade com o
frontend atual.

**Acceptance Scenarios**:

1. **Given** um usuário comum, **When** ele percorre cada tela, **Then** consegue
   fazer tudo o que fazia no frontend atual.

---

### User Story 4 - Administração (Priority: P4)

As telas de administração (painel, conversas, relatórios e impressão,
usuários, sandboxes, modelos, provedores e, para super admin, workspaces,
repositórios e skills globais)
funcionam no frontend novo.

**Why this priority**: Usadas por poucos; podem continuar no frontend atual até
serem portadas.

**Independent Test**: Checklist de paridade por tela, com um administrador.

**Acceptance Scenarios**:

1. **Given** um administrador, **When** ele cria, edita e remove itens em cada
   tela, **Then** o resultado é o mesmo que no frontend atual.

---

### User Story 5 - Virada e remoção do frontend antigo (Priority: P5)

Quando todas as telas tiverem paridade, o frontend novo passa a ser o padrão no
endereço principal e o antigo é removido do produto e do repositório.

**Why this priority**: Encerra a convivência de dois sistemas de design, como
exige a constituição.

**Independent Test**: Acessar o endereço principal, cair no frontend novo, e
confirmar que o antigo não é mais publicado.

**Acceptance Scenarios**:

1. **Given** paridade em todas as telas, **When** a virada é publicada, **Then**
   os endereços antigos levam às telas equivalentes no frontend novo.

### Edge Cases

- Usuário com sessão aberta no frontend atual abre o novo: não precisa entrar de
  novo.
- Tela ainda não portada: o menu do frontend novo leva para ela no frontend
  atual, sem pedir login de novo.
- Falha ao instalar o tema privado no build (token ausente ou sem permissão): o
  build falha com mensagem clara, sem publicar um frontend quebrado.
- Resposta em tempo real interrompida (rede, reinício da API): o chat mostra o
  estado e permite recarregar sem perder a conversa.
- Tela estreita (celular): layout utilizável, menu recolhível.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O frontend novo MUST partir do seed do C3Theme e usar o tema e os
  componentes do pacote do tema, sem copiar o código do tema para o repositório
  do CappyCloud.
- **FR-002**: O frontend novo MUST autenticar no mesmo backend, com as mesmas
  regras de sessão, troca de senha obrigatória e papéis do frontend atual.
- **FR-003**: Cada rota MUST respeitar o mesmo nível de acesso do frontend
  atual (logado, admin, super admin), no menu e no acesso direto pelo endereço.
- **FR-004**: O frontend novo MUST NOT exigir mudança de contrato na API; se uma
  tela precisar de algo novo, isso vira uma tarefa própria da spec.
- **FR-005**: Cada tela portada MUST ter um checklist de paridade com a tela
  atual, executado antes de ser considerada pronta.
- **FR-006**: Textos MUST estar em português do Brasil, incluindo os textos do
  próprio tema.
- **FR-007**: O produto MUST exibir nome e marca do CappyCloud (não o
  placeholder do tema).
- **FR-008**: Enquanto durar a migração, o frontend atual MUST continuar no
  endereço principal e o novo MUST ficar num endereço separado do mesmo domínio.
- **FR-009**: Telas ainda não portadas MUST ser alcançáveis a partir do frontend
  novo, levando ao frontend atual.
- **FR-010**: Depois da virada, o frontend antigo MUST ser removido do build, da
  publicação e do repositório, e as skills de frontend MUST passar a descrever o
  sistema de design novo.
- **FR-011**: O build MUST falhar de forma explícita se não conseguir obter o
  pacote do tema.

### Key Entities

- **Tela portada**: rota do frontend atual, tela equivalente no novo, checklist de
  paridade e estado (pendente, em andamento, com paridade).

### Runtime Context, Security & Evidence *(mandatory when applicable)*

- **RC-001**: Modelo, workspace, repositório, custo e uso continuam vindo da
  conversa, do banco e do catálogo autorizado, como no frontend atual.
- **RC-002**: Mesmas regras de autorização do frontend atual; o código-fonte do
  tema não pode aparecer no repositório público nem em artefatos publicados além
  do bundle do app.
- **RC-003**: N/A.
- **RC-004**: O build da imagem web precisa de credencial de leitura do
  repositório privado do tema, guardada como segredo do CI e nunca no código.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Um usuário existente entra no frontend novo e faz a primeira
  pergunta ao agente em menos de 1 minuto, sem orientação.
- **SC-002**: As 19 telas e os 5 redirecionamentos do frontend atual têm
  equivalente no novo, cada tela com checklist de paridade aprovado, antes da
  virada.
- **SC-003**: Nenhum aumento perceptível no tempo até a primeira resposta do
  agente no chat em relação ao frontend atual.
- **SC-004**: Zero arquivos do tema no repositório público do CappyCloud.
- **SC-005**: Até 2 semanas depois da virada, o frontend antigo não é mais
  publicado nem está no repositório.

## Assumptions

- O dono do produto é dono do C3Theme e a licença do Able Pro cobre o CappyCloud.
- O tema evolui no repositório próprio; melhorias de componente que o CappyCloud
  precisar viram mudança no pacote do tema, não cópia no app.
- O frontend novo fica no mesmo domínio para compartilhar a sessão com o atual.
- A ordem de migração segue as prioridades: esqueleto, chat, telas do usuário,
  administração, virada.
