# Tasks: Conversa no admin igual à do usuário

**Input**: [spec.md](spec.md), [plan.md](plan.md)

## Phase 1: API

- [x] T001 Extrair `load_conversation_activity()` de `conversation_activity.py`
- [x] T002 [US1][US2] `admin_conversation_timeline.py` com atividade, anexos e arquivo, guarda por escopo; registrar no `main.py`
- [x] T003 Testes: 403 fora do escopo, 404 anexo de outra conversa, ligação anexo→pergunta, bytes

## Phase 2: Web

- [x] T004 Funções de API do admin para atividade e anexos
- [x] T005 [US2] Miniaturas reaproveitáveis (`AttachmentTray` exporta `Thumbnail` com loader) e `MessageAttachments`
- [x] T006 [US1][US3] `AdminConversationThread` com `PaperMessage`, `ThinkingStream` e anexos; usar no `AdminConversationsPage`
- [x] T007 Testes vitest da associação e da thread

## Phase 3: Validação

- [ ] T008 Gates da API e da web; revisão no Docker local antes do PR
