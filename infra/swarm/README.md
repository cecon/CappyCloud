# CappyCloud Swarm Deploy

Este diretório contém o stack Portainer/Swarm de produção do CappyCloud.

Evidência usada para o stack:

- `docker-compose.yml` define os serviços locais `postgres`, `redis`, `sandbox`, `api` e `web`.
- `services/api/app/infrastructure/database.py` executa `alembic upgrade head` no boot da API.
- `web/nginx.conf` serve a SPA e encaminha `/api`, `/.well-known` e `/health` para a API.
- `services/api/app/infrastructure/config.py` usa `/var/cappycloud/attachments` como storage de anexos.
- `services/sandbox/session_start.sh` consegue clonar repositórios ausentes a partir de `clone_url`.

## Variáveis obrigatórias no Portainer

- `CAPPYCLOUD_REGISTRY`
- `CAPPYCLOUD_IMAGE_TAG`
- `CAPPYCLOUD_HOST`
- `POSTGRES_PASSWORD`
- `JWT_SECRET`
- `ENCRYPTION_KEY`
- `INTERNAL_API_TOKEN`

Para o fluxo automatico via GitHub Actions + Portainer, configure:

- `CAPPYCLOUD_REGISTRY=ghcr.io/cecon`
- `CAPPYCLOUD_IMAGE_TAG=latest`

O workflow `.github/workflows/container-images.yml` publica as imagens:

- `ghcr.io/cecon/cappycloud-api`
- `ghcr.io/cecon/cappycloud-web`
- `ghcr.io/cecon/cappycloud-sandbox`

Cada imagem recebe duas tags no push para `main`: o SHA curto do commit e
`latest`. O Portainer deve ficar apontado para `latest` e ter o webhook do stack
registrado no secret `PORTAINER_WEBHOOK_URL` do GitHub. Quando existirem
webhooks separados por serviço, registre todos no secret multi-linha
`PORTAINER_WEBHOOK_URLS`. Ao terminar o push das imagens, o workflow chama cada
webhook configurado para o Portainer redeployar e puxar a imagem nova.

Se os packages GHCR estiverem privados, configure tambem a credencial do registry
`ghcr.io` no Portainer com permissao de leitura desses packages. Como alternativa,
deixe os packages publicos.

`OPENROUTER_API_KEY` é opcional quando o provedor/modelo ativo está cadastrado
no banco com chave própria, como Azure. O sandbox ainda recebe um placeholder
não secreto para satisfazer o boot do openclaude; em runtime a API envia a
chave/base URL/formato do provider selecionado no banco por request.

## Persistência

- `cappycloud_postgres_data`: banco PostgreSQL.
- `cappycloud_postgres_backups`: dumps recorrentes `pg_dump -Fc`.
- `cappycloud_redis_data`: Redis persistido.
- `cappycloud_repos_data`: clones e worktrees do sandbox.
- `cappycloud_attachments_data`: anexos das conversas.

O primeiro deploy com migração local deve restaurar o dump do Postgres antes de
liberar uso real. Os anexos locais também devem ser copiados para
`cappycloud_attachments_data` quando existirem registros em `message_attachments`.
