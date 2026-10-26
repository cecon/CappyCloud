# Implementation Plan: Conversa no admin igual à do usuário

**Branch**: `feat/admin-conversation-view` | **Date**: 2026-10-26 | **Spec**: [spec.md](spec.md)

## Summary

Três rotas de leitura novas sob `/api/admin/conversations/{id}` (atividade, lista de anexos, arquivo do anexo), com a guarda de `get_admin_scope`. A tela Admin → Conversas troca o `ChatMessage` simples por uma thread somente leitura que usa `PaperMessage`, `AgentBubble`, `ThinkingStream` (via `buildHistoryTraces`) e as miniaturas do `AttachmentTray`.

## Technical Context

**Language/Version**: Python 3.12 / FastAPI; TypeScript / React
**Storage**: PostgreSQL, sem migration (anexos ligados à pergunta por horário quando `message_id` é nulo)
**Testing**: ruff, ruff format, mypy, pytest (adapter com SQLite), vitest, eslint, tsc
**Constraints**: arquivos até 300 linhas; nenhum vazamento entre workspaces

## Constitution Check

- **I. Spec antes do código**: esta spec/plano/tarefas.
- **II. Hexagonal**: as rotas de admin de conversas já leem o ORM direto; a montagem dos turnos sai de `conversation_activity.py` para uma função reaproveitada pelas duas rotas. O arquivo do anexo é lido pela porta `AttachmentStorage`.
- **III. Gates**: ruff, format, mypy, pytest, vitest, eslint, tsc, build.
- **IV. Segurança**: escopo checado na API antes de ler qualquer dado; testes de 403/404.
- **VI. UX**: mesmos componentes do chat; somente leitura.

## Design

### API (`admin_conversation_timeline.py`)
- `GET /admin/conversations/{id}/activity` → `load_conversation_activity()` (extraída de `conversation_activity.py`).
- `GET /admin/conversations/{id}/attachments` → metadados + `message_id` resolvido + `preview_url` da rota de admin.
- `GET /admin/conversations/{id}/attachments/{att}` → bytes do volume.
- `_conversation_in_scope()`: 404 se a conversa não existe, 403 se o workspace não está no escopo.
- `assign_attachments_to_messages()`: usa `message_id` quando existe; senão, a primeira pergunta com `created_at >= uploaded_at`, ou a última pergunta.

### Web
- `api/adminConversations`: `fetchAdminConversationActivity`, `fetchAdminConversationAttachments`, `fetchAdminAttachmentBlobUrl`.
- `components/admin/AdminConversationThread.tsx`: thread somente leitura.
- `components/MessageAttachments.tsx`: miniaturas de uma pergunta, reaproveitando `Thumbnail`/`AttachmentIcon` exportados do `AttachmentTray` (com loader injetável).
