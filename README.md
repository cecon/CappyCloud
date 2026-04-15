# CappyCloud



AI coding-agent platform that combines:



- **React + Vite + Mantine** — UI própria (login, conversas, streaming)

- **FastAPI** — API REST, JWT, histórico em PostgreSQL

- **[OpenClaude](https://github.com/Gitlawb/openclaude)** — agente em gRPC dentro de sandboxes Docker isoladas

- **OpenRouter** — gateway de modelos (API compatível com OpenAI)

- **PostgreSQL + Redis** — utilizadores/conversas/mensagens + cache/TTL das sessões do agente (`cappy_sessions`)



Each authenticated user session gets its own Docker container with a git workspace. Sessions are isolated, persistent across browser refreshes, and automatically cleaned up after inactivity.



---



## Architecture



```

Browser

  └─ Web estático (Nginx) — porta WEB_PORT (ex.: 38081)

        └─ FastAPI (api:8080 no Docker; host `API_PORT`, p.ex. 38000)

              ├─ PostgreSQL  ← users, conversations, messages + cappy_sessions

              ├─ Redis       ← cache/TTL sandbox

              └─ Docker sandbox containers (por utilizador + conversa)

                    └─ openclaude gRPC server

                          └─ OpenRouter API

```



---



## Prerequisites



- **Docker Desktop** (or Docker Engine + Docker Compose v2)

- An **[OpenRouter API key](https://openrouter.ai/keys)**

- Porta **38081** (ou a definida em `WEB_PORT`) disponível para a UI



---



## Quick Start



### 1. Clone the repository



```powershell

git clone https://github.com/yourorg/cappycloud.git

cd cappycloud

```



### 2. Copy and configure environment variables



```powershell

Copy-Item .env.example .env

```



Edit `.env` and set at minimum:



| Variable | Description |

|---|---|

| `OPENROUTER_API_KEY` | Chave OpenRouter |

| `POSTGRES_PASSWORD` | Password forte do PostgreSQL |

| `JWT_SECRET` | `openssl rand -hex 32` — assinatura dos tokens da API |



### 3. Build the sandbox image



The sandbox image must be built before starting the stack (it clones and

compiles openclaude from source — takes ~2-3 minutes on first build):



```powershell

docker build -t cappycloud-sandbox:latest ./services/sandbox

```



### 4. Start the stack



```powershell

docker compose up -d

```



Services:



| Service | Host port | Internal port | Notes |

|---|---|---|---|

| Web (Nginx + SPA) | **38081** | 80 | `WEB_PORT` no `.env` |

| API (FastAPI) | **38000** (`API_PORT`) | 8080 | Acesso direto à API no host; a UI usa `/api` via Nginx |

| PostgreSQL | 15432 | 5432 | Opcional (debug) |

| Redis | 16379 | 6379 | Opcional (debug) |



> **Port design:** non-standard host ports are used intentionally to avoid collisions

> with common dev tools (Vite, Next.js, CRA all default to 3000).

> O serviço `api` e as portas gRPC dos sandboxes não são expostos no host.



### 5. First login



1. Abra http://localhost:38081 (ou o valor de `WEB_PORT`)

2. Em **Criar conta**, registe o primeiro utilizador (ou use **Entrar**)

3. **Nova conversa** e envie uma mensagem, por exemplo:



   ```

   Analise o repositório https://github.com/torvalds/linux e me diga quantos arquivos .c existem

   ```



   The pipeline will:

   - Detect the GitHub URL and clone the repo into the sandbox

   - Start the openclaude gRPC server

   - Stream the agent's response back in real time



---



## How Sessions Work



```

User A chat #1  ──►  sandbox container A1  (workspace: repo-x)

User A chat #2  ──►  sandbox container A2  (workspace: empty)

User B chat #1  ──►  sandbox container B1  (workspace: repo-y)

```



- One container per `(user_id, chat_id)` pair

- Container reused across multiple messages in the same chat

- Destroyed after `SANDBOX_IDLE_TIMEOUT` seconds of inactivity (default: 30 min)

- Session metadata stored in Redis (fast) + PostgreSQL (persistent)



---



## Configuration Reference



As definições do agente vêm do `.env` (modelo OpenRouter, imagem do sandbox, etc.).



| Variable | Default | Description |

|---|---|---|

| `OPENROUTER_MODEL` | `anthropic/claude-3.5-sonnet` | LLM model for agents (Claude/GPT-4 costumam respeitar melhor os schemas de ferramentas do que modelos só gratuitos) |

| `SANDBOX_IMAGE` | `cappycloud-sandbox:latest` | Docker image to use for sandboxes |

| `DOCKER_NETWORK` | `cappycloud_net` | Docker network name |

| `SANDBOX_GRPC_PORT` | `50051` | Internal gRPC port all sandboxes listen on (no host mapping) |

| `SANDBOX_IDLE_TIMEOUT` | `1800` | Sandbox TTL in seconds |

| `WEB_PORT` | `38081` | Porta do browser para a UI |

| `API_PORT` | `38000` | Porta no host para a FastAPI (container usa 8080, não 8000) |

| `POSTGRES_PORT` | `15432` | PostgreSQL no host (só debug) |

| `REDIS_PORT` | `16379` | Redis no host (só debug) |

| `CORS_ORIGINS` | (derivado de `WEB_PORT` no compose) | Só precisa definir se a UI estiver noutro domínio/porta |



---



## Useful Commands



```powershell

# View all running sandbox containers

docker ps --filter "label=cappycloud.managed=true"



# Watch logs from a specific sandbox

docker logs -f <container_id>



# Stop the entire stack

docker compose down



# Stop and delete all data volumes

docker compose down -v



# Rebuild API e web após alterações ao código

docker compose build api web; docker compose up -d api web

```



---



## Project Structure



```

cappycloud/

├── docker-compose.yml

├── .env.example

├── proto/

│   └── openclaude.proto            # gRPC service definition

├── services/

│   ├── api/                        # FastAPI (auth, conversas, streaming)

│   ├── cappycloud_agent/           # Agente (sandbox Docker + gRPC)

│   ├── pipelines/                  # Legado (Open WebUI); ver README em pipelines/

│   └── sandbox/

│       ├── Dockerfile              # node:20 + openclaude from source

│       └── entrypoint.sh           # Configure + clone + start gRPC

├── web/                            # React + Vite + Mantine

└── README.md

```



---



## Troubleshooting



### Desenvolvimento local (sem Docker)

Na raiz do repo, gere os stubs gRPC em `services/api` ou use `PYTHONPATH` apontando para a pasta onde estão `openclaude_pb2.py`. Alternativa: `docker compose up` só para `postgres` + `redis` e correr `uvicorn` + `npm run dev` no host.



### Sandbox container fails to start



```powershell

# Check sandbox logs

docker logs $(docker ps -lq --filter "label=cappycloud.managed=true")

```



Common causes:

- `OPENROUTER_API_KEY` not set or invalid

- `WORKSPACE_REPO` URL is private (add SSH key or use HTTPS token)

- Port range exhausted — increase `GRPC_PORT_END`



### API ou agente sem resposta



1. `docker compose ps` e `docker compose logs api`

2. Confirme `OPENROUTER_API_KEY` e que a imagem `SANDBOX_IMAGE` existe (`docker images`)



### gRPC timeout on first message



The sandbox container needs time to clone the repository and start openclaude.

Large repos may take > 90 seconds. Increase the wait in `_docker_manager.py`

(`_wait_for_grpc` timeout parameter) or pre-clone in a custom sandbox image.

