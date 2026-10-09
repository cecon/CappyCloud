# Feature Specification: Relatório de uso por workspace

**Feature Branch**: `claude/amazing-poitras-1dc8f1`

**Created**: 2026-10-09

**Status**: Draft

**Input**: Pedido do Alef (admin, time Protheus) para levar à Diretoria/Presidência
o uso do CappyCloud: quantas consultas, quem usou, quanto custou, como evoluiu
por semana e sobre o que foram as consultas. O dono do produto decidiu que a
solução é agnóstica: vale para qualquer workspace (proteus, seller, autosystem,
emsys, smartpos, pdvfacil), com exportação.

## Clarifications

### Session 2026-10-09

Resolvidas com as decisões do dono do produto (sem pergunta bloqueante):

- Q: O que é "branch"? → A: `base_branch` / `branch_name` de cada repo em
  `conversations.repos`; em workspace só leitura é sempre a base (ex.: `main`).
- Q: "Todos" inclui conversas sem workspace? → A: Não; só workspaces visíveis.
- Q: Fuso das datas e das semanas? → A: America/Sao_Paulo, semana ISO.
- Q: Quem define os temas? → A: Taxonomia padrão no código + regras por
  workspace editáveis pelo super admin; proteus nasce com regras de NFS-e.
- Q: CSV ou XLSX? → A: os dois; XLSX com abas para a Diretoria, CSV só das
  consultas. PDF pela página imprimível do navegador.
- Q: R$? → A: fora desta entrega (sem fonte de câmbio configurada).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Ver o uso de um workspace num período (Priority: P1)

Um admin abre Admin → Relatórios, escolhe o workspace (ou "Todos"), o período
(atalhos 7/15/30/90 dias ou datas livres) e, se quiser, a branch dos
repositórios. A página mostra o número de consultas, analistas distintos, custo
total, custo médio por consulta e por analista, a tabela por analista e a
evolução semanal.

**Why this priority**: é o número que a Diretoria pede; sem ele o resto não tem
contexto.

**Independent Test**: com conversas de dois workspaces e de dois analistas em
datas diferentes, chamar o endpoint com cada filtro e conferir contagens,
custos e semanas.

**Acceptance Scenarios**:

1. **Given** 3 conversas do proteus com mensagens no período e 1 só fora dele,
   **When** o admin pede o relatório do proteus nesse período, **Then** vê 3
   consultas e o custo é a soma de `cost_usd` das mensagens dentro do período.
2. **Given** dois analistas no período, **When** o relatório abre, **Then** a
   tabela por analista lista cada e-mail com suas consultas e custo, e o custo
   médio por analista é o custo total dividido por 2.
3. **Given** mensagens em duas semanas ISO diferentes, **When** o relatório
   abre, **Then** a evolução semanal mostra as duas semanas (e as semanas sem
   uso dentro do período com zero).
4. **Given** conversas na branch `main` e na `master`, **When** o admin filtra
   por `main`, **Then** só as conversas cujos repositórios usam `main` (base ou
   branch de trabalho) entram.

---

### User Story 2 - Ver sobre o que foram as consultas (Priority: P2)

O relatório agrupa as consultas por tema (ex.: no proteus, "NFS-e: Schema /
layout XML", "NFS-e: Retenções"), com quantidade e custo por tema, e o que não
casar com nenhum tema cai em "Outros".

**Why this priority**: a Diretoria quer saber em que o time usa a ferramenta,
mas a métrica de volume e custo vale sozinha.

**Independent Test**: com títulos conhecidos, conferir o tema atribuído a cada
consulta e os totais por tema.

**Acceptance Scenarios**:

1. **Given** uma consulta "Análise a rejeição E370 - outras retenções",
   **When** o relatório do proteus abre, **Then** ela conta no tema de
   retenções.
2. **Given** uma consulta "ola", **When** o relatório abre, **Then** ela conta
   em "Outros".
3. **Given** um super admin, **When** ele edita as regras de temas do
   workspace, **Then** o próximo relatório usa as regras novas; regra com
   expressão inválida é recusada com mensagem clara.
4. **Given** um workspace sem regras próprias, **When** o relatório abre,
   **Then** usa a taxonomia padrão genérica.

---

### User Story 3 - Exportar para levar à Diretoria (Priority: P2)

O admin baixa uma planilha (XLSX) com o resumo, a tabela por analista, as
semanas, os temas e a lista de consultas, ou um CSV com as consultas; e abre uma
versão imprimível (salvar como PDF pelo navegador) com o mesmo conteúdo.

**Why this priority**: o destino final do relatório é uma apresentação.

**Independent Test**: baixar o XLSX e o CSV com um filtro e conferir que as
linhas batem com a tela; abrir a página imprimível e conferir os blocos.

**Acceptance Scenarios**:

1. **Given** um filtro aplicado, **When** o admin exporta, **Then** o arquivo
   tem só as consultas do filtro e os valores em US$ de `cost_usd`.
2. **Given** a página imprimível, **When** é impressa, **Then** filtros,
   navegação e botões não aparecem e o cabeçalho mostra workspace, período,
   branch e a data de geração.

---

### User Story 4 - Admin só vê os seus workspaces (Priority: P1)

Super admin vê todos os workspaces. Admin comum só vê os workspaces que tem em
`user_workspace_access`; pedir outro devolve 403.

**Independent Test**: admin com acesso só ao proteus pede o seller → 403;
pede "Todos" → só o proteus entra.

**Acceptance Scenarios**:

1. **Given** admin comum sem acesso ao seller, **When** pede o relatório do
   seller (tela ou exportação), **Then** recebe 403.
2. **Given** admin comum com acesso ao proteus, **When** pede "Todos",
   **Then** só as consultas do proteus entram e a lista de workspaces do filtro
   só tem o proteus.
3. **Given** usuário não admin, **When** chama qualquer rota do relatório,
   **Then** recebe 403.

### Edge Cases

- Período sem consultas: zeros e médias zero, sem divisão por zero.
- Data início depois da data fim, ou período maior que 366 dias: 422 com
  mensagem clara.
- Conversa sem workspace: não entra em nenhum relatório de workspace.
- Mensagens sem `cost_usd` (nulo): contam a consulta, custo zero.
- Conversa com mensagens antes e dentro do período: só o custo dentro do
  período conta; ela conta como consulta do período.
- Semana ISO que cruza o ano (ex.: 2026-W53 / 2027-W01): rótulo pelo ano ISO.
- Branch filtrada que não existe no workspace: relatório vazio, não erro.
- Admin comum sem nenhum workspace concedido: "Todos" devolve relatório vazio.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O sistema MUST aceitar filtros `workspace_id` (opcional; ausente
  = todos os workspaces visíveis), `branch` (opcional), `start` e `end` (datas,
  inclusivas, no fuso America/Sao_Paulo).
- **FR-002**: Consulta MUST ser uma conversa do escopo com ao menos uma
  mensagem criada dentro do período.
- **FR-003**: Custo MUST ser a soma de `messages.cost_usd` das mensagens dentro
  do período (dado real do provedor); nenhuma estimativa local.
- **FR-004**: O relatório MUST trazer: consultas, analistas distintos, custo
  total, custo médio por consulta, custo médio por analista, tabela por
  analista (e-mail, consultas, custo), evolução por semana ISO (consultas e
  custo, semanas vazias com zero), distribuição por tema (consultas e custo) e,
  quando "Todos", a quebra por workspace.
- **FR-005**: O analista MUST ser identificado pelo e-mail do usuário; nenhum
  nome inventado.
- **FR-006**: As opções do filtro MUST listar os workspaces visíveis ao admin e
  as branches distintas (`base_branch` e `branch_name` de `conversations.repos`)
  das conversas do escopo.
- **FR-007**: O tema MUST ser atribuído por regras determinísticas (expressões
  regulares sem diferença de maiúsculas e acentos) sobre o título e a primeira
  mensagem do usuário; a primeira regra que casar vence; sem regra, "Outros".
- **FR-008**: Cada workspace MUST poder ter regras próprias; sem elas, vale a
  taxonomia padrão genérica. Só o super admin edita; regras inválidas
  (expressão que não compila, chave repetida, chave reservada `outros`, mais de
  30 temas) são recusadas com 422.
- **FR-009**: Exportação MUST oferecer XLSX (resumo, analistas, semanas, temas,
  consultas) e CSV (consultas), com os mesmos filtros e as mesmas regras de
  acesso.
- **FR-010**: MUST existir uma página imprimível do relatório, com cabeçalho
  de filtros e data de geração, sem controles na impressão.
- **FR-011**: Valores monetários MUST ser em US$; o relatório não converte para
  R$ nesta entrega.

### Key Entities

- **Consulta do relatório**: conversa do escopo com mensagens no período;
  workspace, analista (e-mail), chamado, título, branches, tema, mensagens e
  custo no período, primeira e última mensagem no período.
- **Regras de tema**: lista ordenada por workspace de `{key, label, patterns}`.
- **Relatório**: filtros aplicados, totais, médias, analistas, semanas, temas,
  workspaces.

### Runtime Context, Security & Evidence *(mandatory when applicable)*

- **RC-001**: Custo vem só de `messages.cost_usd` (AGENTS.md, "Modelos e
  custo"). Nada de modelo ou LLM é chamado pelo relatório.
- **RC-002**: Rotas exigem papel admin. Admin comum fica restrito aos workspaces
  de `user_workspace_access` (403 fora deles); edição de temas exige super
  admin. Testes negativos cobrem os três casos.
- **RC-003**: N/A (sem documentação externa).
- **RC-004**: N/A (sem sandbox, Git ou rede).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Um admin monta o relatório de um workspace num período e exporta
  em menos de 1 minuto, sem consultar o banco.
- **SC-002**: Os totais da tela, do XLSX e do CSV são idênticos para o mesmo
  filtro.
- **SC-003**: Nas conversas reais do proteus até 2026-10-09, ao menos 80% das
  consultas com assunto técnico caem num tema diferente de "Outros".
- **SC-004**: O relatório de 90 dias responde em menos de 2 segundos com o
  volume atual (centenas de conversas).

## Assumptions

- "Todos" significa todos os workspaces visíveis ao admin; conversas sem
  workspace ficam de fora.
- Datas no fuso America/Sao_Paulo (usuários no Brasil); semanas ISO
  (segunda a domingo) no mesmo fuso.
- O tema é da conversa inteira (título e primeira mensagem), não do período.
- Classificação por LLM fica como opção futura documentada, não implementada.
- Cotação em R$ fica fora: exigiria fonte real de câmbio e não foi pedida como
  obrigatória.
