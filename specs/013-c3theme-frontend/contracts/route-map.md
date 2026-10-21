# Contract: mapa de rotas

Durante a migração o `web-c3` é servido em `/c3/` e o `web/` em `/`. Cada tela
do inventário (`data-model.md`) tem uma rota no `web-c3` com o mesmo caminho
relativo: `/chat` → `/c3/chat`, `/admin/users` → `/c3/admin/users` etc.

## Regras

1. Menu do `web-c3`: tela com estado `paridade` ou `em andamento` publicada abre
   `/c3/<rota>`; tela `pendente` abre `/<rota>` (frontend atual). A lista de
   telas portadas fica num único arquivo do `web-c3` (`src/routes/ported.ts`),
   atualizado no PR de cada tela.
2. Acesso direto a `/c3/<rota>` de uma tela pendente redireciona para `/<rota>`.
3. Nível de acesso por rota igual ao do `web/` (logado, admin, super admin),
   checado no menu e na rota.
4. `/c3/` é o Início no layout novo (lista as telas e o estado de cada uma);
   rotas desconhecidas → `/c3/`. Na virada, o início volta a ser o chat.
   Redirecionamentos do `web/` são replicados: `/c3/register` → `/c3/login`;
   `/c3/environments` → `/c3/`; `/c3/admin/agents-global` → `/c3/admin/sandboxes`.
5. Sessão: o `web-c3` lê e grava o token na mesma chave de `localStorage` do
   `web/`; sair num app sai nos dois.

## Virada (US5)

- `web-c3` passa a ser servido em `/` com `base: '/'`.
- `/c3/<rota>` redireciona (301) para `/<rota>` por um período, para links
  salvos.
- O `web/` deixa de ser construído e é removido do repositório.
