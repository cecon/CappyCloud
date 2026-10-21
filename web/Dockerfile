# Build a partir da raiz do repositório:
#   docker build -f web/Dockerfile --secret id=c3theme_token,env=C3THEME_READ_TOKEN .
#
# Constrói dois apps na mesma imagem enquanto a migração para o C3Theme não
# termina (specs/013-c3theme-frontend): web/ em / e web-c3/ em /c3/.

FROM node:20-alpine AS build
RUN corepack enable && corepack prepare pnpm@10.27.0 --activate
WORKDIR /app
COPY web/package.json web/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY web/ ./
RUN pnpm run build

FROM node:22-alpine AS build-c3
RUN apk add --no-cache git && corepack enable && corepack prepare pnpm@10.32.1 --activate
WORKDIR /app/web-c3
COPY web-c3/package.json web-c3/pnpm-lock.yaml ./
# O tema vem do repositório privado cecon/C3Theme (contracts/theme-dependency.md).
# O token só existe neste RUN, via variáveis do git: não fica em nenhuma camada.
RUN --mount=type=secret,id=c3theme_token,required=true \
    TOKEN="$(cat /run/secrets/c3theme_token)" \
    && GIT_CONFIG_COUNT=1 \
       GIT_CONFIG_KEY_0="url.https://x-access-token:${TOKEN}@github.com/cecon/C3Theme.insteadOf" \
       GIT_CONFIG_VALUE_0="https://github.com/cecon/C3Theme" \
       pnpm install --frozen-lockfile
# A camada de dados do web/ é compartilhada pelo alias @cappy (research R3).
COPY web/src /app/web/src
COPY web-c3/ ./
RUN pnpm run build

FROM nginx:1.27-alpine
COPY web/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
COPY --from=build-c3 /app/web-c3/dist /usr/share/nginx/html/c3
# Escuta 80 no container; no host o mapeamento é `WEB_PORT` no docker-compose
EXPOSE 80
