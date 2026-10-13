# Research: Frontend do CappyCloud no C3Theme

## R1. Como instalar o tema privado

- **Decision**: `"@c3theme/ui": "github:cecon/C3Theme#<sha>&path:/packages/ui"`
  no `web-c3/package.json`, com commit fixo. Atualizar o tema = trocar o sha.
- **Rationale**: testado em 2026-10-13 com pnpm 10.32.1: instalou o pacote do
  commit `b2685230c529bebaff8cb283faaabff897fc4eb7` (139 dependências, 28 s). O
  pacote exporta o código TypeScript (`exports: ./src/index.ts`) e usa só
  imports relativos, então o Vite do app compila sem configuração extra.
- **Credencial**: local, a do git do desenvolvedor. No CI e no
  `docker build`, um token de leitura só do `cecon/C3Theme`, passado como
  BuildKit secret (`--mount=type=secret`) e usado por
  `git config url.<token>.insteadOf` só durante o `pnpm install`. O token não
  entra em camada da imagem nem no lockfile.
- **Alternatives considered**: copiar `packages/ui` (publica código do Able
  Pro); submódulo git (mesma credencial, mais atrito no dia a dia); registro npm
  privado (infra nova sem ganho agora).

## R2. Onde servir o app novo

- **Decision**: mesma imagem `cappycloud-web`; build do `web-c3` com
  `base: '/c3/'` copiado para `/usr/share/nginx/html/c3`; nginx com
  `location /c3/ { try_files $uri $uri/ /c3/index.html; }`.
- **Rationale**: mesma origem, então o token no `localStorage` vale nos dois
  apps (spec: não pedir login de novo); `/api` já é proxied pelo nginx; sem rota
  nova no Traefik nem serviço novo no Dokploy.
- **Alternatives considered**: subdomínio (sessão não compartilhada); serviço
  separado (mais infra para algo temporário).

## R3. Reaproveitar a lógica do `web/`

- **Decision**: alias `@cappy` → `../web/src`, usado só por `web-c3/src/data/`,
  que reexporta o cliente HTTP (`api.ts`), validações e hooks sem UI. Telas do
  `web-c3` importam de `data/`, nunca de `@cappy` direto.
- **Rationale**: uma só implementação de chamadas, streaming e regras de sessão
  enquanto os dois apps convivem; na virada, os arquivos de dados são movidos
  para `web-c3/src/data/` e o alias some.
- **Alternatives considered**: copiar `api.ts` (duas versões divergindo durante
  meses); pacote compartilhado (estrutura nova para algo temporário).

## R4. Seed como referência

- **Decision**: seguir a organização do seed (`config.ts`, `menu-items/`,
  `routes/`, `Locales`, `C3ThemeProvider`, `DashboardLayout` do pacote) com código
  escrito para o CappyCloud. Não trazer: ilustrações de manutenção, avatares,
  widgets de mensagens/notificações, páginas de cadastro e recuperação de senha
  (o CappyCloud não tem).
- **Rationale**: decisão do dono do produto (spec, Clarifications). Componente
  que faltar no pacote entra no `@c3theme/ui`, não no app (convenção do
  C3Theme).

## R5. Menu durante a migração

- **Decision**: o menu do `web-c3` lista todas as telas desde o primeiro PR. Tela
  portada abre dentro do `/c3/`; tela pendente abre a rota equivalente do
  `web/` (mesma sessão). O estado vem de `contracts/route-map.md`.
- **Rationale**: FR-009; o usuário pode usar só o app novo desde o início.

## R6. Garantir que nada do tema vaze

- **Decision**: verificação no CI que falha se `web-c3/` tiver arquivos de
  imagem de manutenção/avatar do Able Pro ou textos de licença do fornecedor
  (lista de nomes e padrões em `contracts/theme-dependency.md`), além da
  revisão de cada PR.
- **Rationale**: SC-004 precisa ser verificável, não só uma intenção.

## R7. Versões

- **Decision**: React Router 8 no `web-c3` (o tema exige `react-router@^8`); o
  `web/` segue no 7 até ser removido. MUI, Emotion, react-intl e SWR nas versões
  do seed.
- **Rationale**: apps separados com lockfiles separados; não há conflito.
