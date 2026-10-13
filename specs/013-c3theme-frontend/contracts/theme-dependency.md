# Contract: dependência do tema privado

## Declaração

`web-c3/package.json`:

```json
"@c3theme/ui": "github:cecon/C3Theme#<sha>&path:/packages/ui"
```

- `<sha>` é um commit do `cecon/C3Theme`; nunca branch. Atualizar o tema é um PR
  que troca o sha e roda os checks.
- O pacote é TypeScript fonte; o Vite do `web-c3` compila.

## Credencial

| Onde | Como |
|---|---|
| Máquina do desenvolvedor | credencial git normal (quem tem acesso ao repo privado) |
| CI de frontend (lint/build) | segredo `C3THEME_READ_TOKEN`, usado em `git config --global url."https://x-access-token:${TOKEN}@github.com/cecon/C3Theme".insteadOf "https://github.com/cecon/C3Theme"` antes do `pnpm install` |
| Build da imagem web | o mesmo segredo como BuildKit secret (`--mount=type=secret,id=c3theme_token`), só no passo do `pnpm install` |

`C3THEME_READ_TOKEN`: token de leitura (fine-grained, só o repositório
`cecon/C3Theme`, permissão Contents: read). Criado pelo dono do repositório.

Sem o token, o `pnpm install` falha com erro de autenticação do git, e o build
para (FR-011).

## O que nunca entra no repositório público

- Arquivos de `packages/ui` ou de `apps/*` do C3Theme copiados para o CappyCloud.
- Arte do Able Pro: `img-error-404.svg`, `img-error-500.svg`, `img-soon-*`,
  `img-construction-*`, `img-cunstruct-*`, `message*.svg` de widget,
  `avatar-*.png`.
- Textos de licença ou cabeçalhos do fornecedor ("Phoenixcoded", "Able Pro").

A verificação do CI (R6) procura esses nomes e textos em `web-c3/` e falha se
encontrar.
