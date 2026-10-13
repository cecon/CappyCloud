# Quickstart: frontend C3

## Rodar local

Pré-requisitos: Node 22+, pnpm 10 e acesso de leitura ao `cecon/C3Theme`.

```bash
pnpm --dir web-c3 install
pnpm --dir web-c3 dev        # http://localhost:5175/c3/
```

O Vite do `web-c3` encaminha `/api` para a API local, como o `web/`.

## Checks

```bash
pnpm --dir web-c3 lint
pnpm --dir web-c3 typecheck
pnpm --dir web-c3 build
pnpm --dir web-c3 test
```

## Validar o esqueleto (US1)

1. Abrir `/c3/`, entrar com uma conta existente: cai no chat (ou na tela
   pendente do `web/`), com o layout C3, nome CappyCloud e textos em português.
2. Conta com troca de senha obrigatória: vai para `/c3/change-password` antes de
   qualquer outra tela.
3. Usuário comum: o menu não mostra administração; `/c3/admin` leva ao chat.
4. Abrir `/chat` (frontend atual) na mesma aba: continua logado.
5. Sair no `web-c3`: `/chat` também pede login.
6. Alternar tema claro/escuro e recarregar: a escolha permanece.

## Validar uma tela portada

Executar o checklist de paridade de `data-model.md` lado a lado com a tela do
`web/`, e marcar o estado da tela no inventário no mesmo PR.
