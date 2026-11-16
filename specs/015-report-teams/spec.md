# Feature Specification: Times no relatório

**Feature Branch**: `feat/report-teams`
**Created**: 2026-11-16
**Status**: Draft
**Input**: Rodolfo (admin do PROTHEUS) quer ver o uso por time ("Protheus Suporte, Protheus Prime, Protheus Prime Ágil..."). Mandou em 13/11 a lista de qual e-mail é de qual time e disse que os e-mails novos serão vinculados "na tela de usuários".

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Admin cadastra os times do workspace (Priority: P1)

Rodolfo abre Admin → Workspaces → PROTHEUS → Times e cria, renomeia ou apaga times (PROTHEUS SPED, PROTHEUS PRIME SP...).

**Independent Test**: como admin do PROTHEUS, criar "PROTHEUS SPED"; ele aparece na lista do workspace; nome repetido (sem diferenciar maiúsculas) dá 409; admin de outro workspace recebe 403.

**Acceptance Scenarios**:

1. **Given** admin do workspace (ou ADMIN global), **When** cria um time, **Then** o time passa a existir só naquele workspace.
2. **Given** um time com pessoas, **When** é apagado, **Then** as pessoas ficam "Sem time" (acesso ao workspace continua).
3. **Given** um time, **When** é renomeado, **Then** o relatório passa a mostrar o nome novo, inclusive para períodos passados.

### User Story 2 - Admin vincula a pessoa a um time (Priority: P1)

Em Admin → Usuários → Acessos → Workspaces, na linha do PROTHEUS, escolhe o time da pessoa.

**Independent Test**: escolher "PROTHEUS SPED" para gabriel.mota no PROTHEUS-azure; `GET` dos acessos devolve o time; escolher "Sem time" limpa.

**Acceptance Scenarios**:

1. **Given** pessoa sem acesso ao workspace, **When** recebe um time, **Then** o acesso é concedido junto.
2. **Given** um time de outro workspace, **When** é enviado, **Then** 422.
3. **Given** admin de workspace, **When** mexe no time de um ADMIN global ou fora do seu workspace, **Then** 403 (mesmas regras de conceder acesso).

### User Story 3 - Relatório por time (Priority: P1)

Em Relatórios aparece o filtro "Time" e um quadro "Por time" (pessoas, consultas, conversas, custo e % das consultas). A tabela de analistas e a de conversas ganham a coluna Time, e a exportação também.

**Independent Test**: com duas pessoas em times diferentes, o quadro soma cada time separado; filtrar por um time deixa só as conversas das pessoas daquele time; quem não tem time aparece como "Sem time".

**Acceptance Scenarios**:

1. **Given** relatório do PROTHEUS-azure, **When** filtra "PROTHEUS SPED", **Then** totais, semanas, temas, analistas e conversas consideram só esse time.
2. **Given** relatório de vários workspaces, **When** a mesma pessoa tem times diferentes em cada um, **Then** cada conversa conta para o time da pessoa no workspace da conversa.
3. **Given** o filtro "Sem time", **Then** aparecem só conversas de quem não tem time no workspace.

### Edge Cases

- Time vale no momento da consulta ao relatório (não há histórico de troca de time).
- Pessoa que perdeu o acesso ao workspace: suas conversas antigas aparecem como "Sem time".
- Nome de time: 1 a 128 caracteres, espaços nas pontas removidos.

## Requirements *(mandatory)*

- **FR-001**: times pertencem a um workspace; nome único por workspace sem diferenciar maiúsculas.
- **FR-002**: ADMIN global e admin do workspace criam, renomeiam e apagam times; listar times também é permitido a eles.
- **FR-003**: cada acesso pessoa↔workspace tem no máximo um time; apagar o time limpa o vínculo.
- **FR-004**: definir o time segue as regras de conceder acesso (admin de workspace só USER comum do seu workspace) e concede o acesso se faltar.
- **FR-005**: o relatório aceita filtro de time (por nome; "__none__" = sem time), lista os times do escopo nas opções e devolve o quadro por time.
- **FR-006**: analistas, conversas e exportações CSV/XLSX mostram o time.

## Success Criteria *(mandatory)*

- **SC-001**: Rodolfo cadastra os 6 times e vincula as 26 pessoas da lista sem ajuda.
- **SC-002**: o quadro "Por time" soma exatamente o total do relatório.
