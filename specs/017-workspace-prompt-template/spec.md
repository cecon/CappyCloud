# 017 — Prompt modelo por workspace

## Pedido

Alef (admin do PROTHEUS-azure), 2026-11-25: o pessoal começa as conversas de
jeitos muito diferentes. Ele quer padronizar a primeira mensagem com um
"prompt modelo" cadastrado no workspace, só texto. Toda conversa nova do
workspace abre com esse texto já na caixa de mensagem, e a pessoa completa e
edita antes de enviar. O texto não é enviado automaticamente.

## Regras

- O campo `prompt_template` do workspace é texto puro, com no máximo 8000
  caracteres. Vazio é o padrão e mantém o comportamento de antes: a caixa abre
  vazia.
- Quem edita: o super admin e o admin do workspace, com a mesma regra do
  CLAUDE.md (`WORKSPACE_ADMIN_FIELDS`).
- O chat recebe o modelo em `GET /api/workspaces/accessible` (`prompt_template`).
- Conversa nova (sem conversa aberta): a caixa recebe o modelo do workspace
  selecionado, nestes casos:
  - quando a caixa está vazia;
  - quando a caixa ainda contém o modelo anterior, depois de uma troca de
    workspace.
- O que a pessoa digitou nunca é apagado. Se ela apagar o modelo, a caixa fica
  vazia até ela trocar de workspace ou abrir outra conversa nova.
- Conversa já aberta não recebe o modelo.

## Implementação

- Migration `3c7e2a9d5b41`: `workspaces.prompt_template TEXT NOT NULL DEFAULT ''`.
- API:
  - `schemas_workspaces.py`: campo nos schemas Create, Update e Out.
  - `admin_workspaces.py`: create, update e `_serialize`.
  - `workspaces_accessible.py`: campo novo na resposta.
- Web:
  - campo "Prompt modelo" no formulário do workspace (`WorkspaceFormModal.tsx`);
  - preenchimento da caixa de mensagem em `pages/chat/usePromptTemplate.ts`.

## Testes

- `tests/adapter/test_workspace_prompt_template.py`:
  - o admin do workspace grava o modelo e não consegue gravar em outro
    workspace;
  - o chat recebe o modelo;
  - o padrão é vazio e o limite é 8000.
- `web/src/pages/chat/usePromptTemplate.test.ts`:
  - a caixa recebe o modelo e troca junto com o workspace;
  - o texto digitado pela pessoa não é apagado;
  - conversa aberta não recebe o modelo.
