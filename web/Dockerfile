# Build a partir da raiz do repositório:
#   docker build -f web/Dockerfile .

FROM node:20-alpine AS build
WORKDIR /app
COPY web/package*.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

FROM nginx:1.27-alpine
COPY web/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
# Escuta 80 no container; no host o mapeamento é `WEB_PORT` no docker-compose
EXPOSE 80
