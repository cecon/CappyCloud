# Feature Specification: Conversa no admin igual à do usuário

**Feature Branch**: `feat/admin-conversation-view`
**Created**: 2026-10-26
**Status**: Draft
**Input**: pedido do Alef (dono do workspace PROTHEUS) no Google Chat, 26/10/2026: lendo as conversas no admin não dá para entender o que aconteceu, porque não aparecem os anexos que o usuário colocou nem os passos da Cappy. Ele quer a tela igual à do usuário.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Admin vê os passos do agente em cada resposta (Priority: P1)

O admin abre uma conversa em Admin → Conversas e, abaixo de cada pergunta, vê a mesma linha do tempo de passos que o usuário vê no chat (ferramentas, comandos, status, erro, interrupção).

**Why this priority**: sem os passos não dá para saber por que a Cappy respondeu o que respondeu.

**Independent Test**: como admin do PROTHEUS, abrir uma conversa do PROTHEUS com turnos; `GET /api/admin/conversations/{id}/activity` devolve os turnos e a tela mostra os passos sob cada pergunta.

**Acceptance Scenarios**:

1. **Given** uma conversa com turnos registrados, **When** o admin abre a conversa, **Then** cada pergunta mostra os passos do turno, como no chat.
2. **Given** admin de outro workspace, **When** pede a atividade dessa conversa, **Then** recebe 403.
3. **Given** um USER sem papel de admin, **When** chama a rota, **Then** recebe 403.

### User Story 2 - Admin vê os anexos que o usuário mandou (Priority: P1)

Prints aparecem como miniatura junto da pergunta em que foram enviados; outros arquivos aparecem com ícone e nome. Clicar abre o arquivo.

**Independent Test**: conversa com um print enviado antes da 2ª pergunta; `GET /api/admin/conversations/{id}/attachments` devolve o anexo com `message_id` da 2ª pergunta e `GET .../attachments/{att}` devolve os bytes.

**Acceptance Scenarios**:

1. **Given** um anexo enviado com uma pergunta, **When** o admin abre a conversa, **Then** a miniatura aparece nessa pergunta.
2. **Given** admin de outro workspace, **When** pede a lista ou o arquivo, **Then** recebe 403.
3. **Given** um id de anexo de outra conversa, **When** pedido nesta conversa, **Then** recebe 404.

### User Story 3 - Mesma aparência do chat (Priority: P2)

As mensagens usam os mesmos balões do chat (usuário à direita, Cappy com avatar, markdown, uso do modelo), em modo somente leitura: nada é enviado em nome do usuário.

### Edge Cases

- Anexo sem `message_id` (todos os antigos: o envio não grava a ligação) fica na primeira pergunta enviada depois do upload; se não houver pergunta depois, fica na última pergunta.
- Conversa sem turnos registrados: mostra só as mensagens.
- Arquivo apagado do volume: a miniatura falha sozinha e mostra o ícone; o resto da conversa abre.

## Requirements *(mandatory)*

- **FR-001**: A API MUST expor, só para leitura, a atividade e os anexos de qualquer conversa ao ADMIN global e ao admin do workspace da conversa.
- **FR-002**: A guarda MUST ser a mesma das rotas atuais de conversas do admin (404 conversa inexistente, 403 fora do escopo).
- **FR-003**: Cada anexo MUST vir associado a uma pergunta do usuário.
- **FR-004**: A tela MUST reaproveitar os componentes do chat (balão, passos, miniaturas), sem ações de escrita.

## Success Criteria *(mandatory)*

- **SC-001**: Um admin do PROTHEUS abre uma conversa e vê anexos e passos como o usuário viu.
- **SC-002**: Nenhuma rota nova devolve dado de conversa fora do escopo do admin (testes de 403).
