# CappyCloud — Arquitetura

## Visão Geral

CappyCloud é uma plataforma de agentes IA: backend FastAPI + frontend React +
agentes openclaude rodando em sandboxes Docker com git worktrees por conversa.

Decisões de base:

- [ADR-001](decisions/adr-001-hexagonal-architecture.md) — Arquitetura
  Hexagonal da API
- [ADR-002](decisions/adr-002-sandbox-runtime-and-worktree-sessions.md) —
  Runtime sandbox e sessões por worktree
- [ADR-003](decisions/adr-003-on-demand-semantic-code-tooling.md) —
  Ferramentas semânticas LSP/AST sob demanda

## Arquitetura Hexagonal (Ports & Adapters)

```
┌─────────────────────────────────────────────────────────┐
│  Primary Adapters (driving)                             │
│  app/adapters/primary/http/  ← FastAPI routers (thin)  │
└────────────────┬────────────────────────────────────────┘
                 │ calls use cases
┌────────────────▼────────────────────────────────────────┐
│  Application Layer                                      │
│  app/application/use_cases/  ← ALL business logic here │
└────────────────┬────────────────────────────────────────┘
                 │ uses ports (ABCs)
┌────────────────▼────────────────────────────────────────┐
│  Ports (interfaces)                                     │
│  app/ports/  ← ABCs: UserRepository, AgentPort, etc.   │
└────────────────┬────────────────────────────────────────┘
                 │ implemented by
┌────────────────▼────────────────────────────────────────┐
│  Secondary Adapters (driven)                            │
│  app/adapters/secondary/  ← SQLAlchemy, Pipeline, etc. │
└─────────────────────────────────────────────────────────┘
```

## Directory Map

```
services/api/
  app/
    domain/          Pure Python entities + value objects (zero external imports)
    ports/           ABCs only — no implementations here
    application/     Use cases (orchestrate domain + ports)
    adapters/
      primary/http/  FastAPI routers + DI wiring (deps.py)
      secondary/     SQLAlchemy repos, PipelineAdapter, security services
    infrastructure/  config.py, database.py, security.py, orm_models.py
    schemas.py       Pydantic HTTP contracts (validators delegate to domain)
    main.py          FastAPI app + lifespan wiring only

tests/
  conftest.py        In-memory fakes + shared fixtures
  unit/              Test use cases + domain (no DB, no HTTP)
  adapter/           LSP contract tests (parametrized)
  integration/       Full HTTP tests via httpx + dependency_overrides

services/cappycloud_agent/
  cappycloud_pipeline.py   Pipeline principal (orquestra tudo)
  _environment_manager.py  Gerencia sessões por conversa no sandbox
  _grpc_session.py         Sessão gRPC persistente por (user_id, chat_id)
  _session_store.py        Persistência de sessões (Redis + PostgreSQL)
  _grpc_bridge.py          Bridge HTTP → gRPC para uso externo

services/sandbox/
  Dockerfile               Runtime do agente, ferramentas e openclaude
  session_server.js        Sidecar HTTP para sessões, worktrees e Git
  session_start.sh         Criação idempotente de worktrees por sessão

proto/
  openclaude.proto         Contrato gRPC do servidor openclaude

web/                       Frontend React (Vite + TypeScript)
```

## Arquitetura do Agente

O agente openclaude roda **dentro** de um sandbox Docker e se comunica via gRPC.
O sandbox também expõe um `session_server` HTTP interno usado para criar
sessões e worktrees.

Para a feature `008-openclaude-current-upgrade`, o sandbox mira OpenClaude
`0.28.0` no commit `6e30b40de00868a968bdcaa0c3d0dd915d69d357`. A validação
é local; rollout de produção fica fora do escopo da implementação e deve
seguir o runbook em `docs/how-to/openclaude-v027-rollout.md`.

```
Usuário envia mensagem
       ↓
  Pipeline (cappycloud_pipeline.py)
       ↓  resolve modelo e permission_mode da conversa
       ↓  garante sandbox acessível e sessão criada
  EnvironmentManager (_environment_manager.py)
       ↓  HTTP interno para session_server
  /repos/sessions/<session_id>/<repo-alias>
       ↓
  GrpcSession (_grpc_session.py)
       ↓  stream gRPC bidirecional persistente
  openclaude (gRPC :50051 no sandbox)
       ↓
  LLM via OpenRouter
```

### Componentes do agente

| Classe | Arquivo | Responsabilidade |
|---|---|---|
| `Pipeline` | `cappycloud_pipeline.py` | Ponto de entrada; roteia mensagens para a sessão correta |
| `EnvironmentManager` | `_environment_manager.py` | Cria/reusa sessões no sandbox e garante worktrees por conversa |
| `GrpcSession` | `_grpc_session.py` | Stream gRPC persistente; pausa em `ActionRequired`, retoma com `send_input()` |
| `SessionStore` | `_session_store.py` | Estado das sessões em Redis (TTL) + PostgreSQL (histórico) |

### Contrato de modo de permissões

O modo de permissões é configuração da conversa, não variável global do
sandbox. `Conversation.permission_mode` usa os valores
`request_permissions`, `accept_edits`, `plan`, `auto` ou
`bypass_permissions`.

Fluxo:

1. A UI envia `permission_mode` em
   `POST /api/conversations/{id}/messages/stream`.
2. `StreamMessage` valida o valor no domínio, persiste na conversa e coloca o
   modo resolvido no corpo enviado ao `AgentPort`.
3. `cappycloud_pipeline.py` sanitiza fallback para `bypass_permissions`.
4. `_grpc_session.py` envia `permission_mode` em cada `ChatRequest`.
5. O patch gRPC do OpenClaude aplica o modo por request, depois dos guardrails
   de worktree do CappyCloud.

`auto` e `bypass_permissions` só ignoram prompts de permissão do OpenClaude;
na UI, `bypass_permissions` aparece como **Acesso completo**.
Autorização de repositório, isolamento do sandbox, guardas de path/worktree,
redação de segredos e gates explícitos de ações externas continuam ativos.

### Ferramentas do sandbox

O sandbox inclui ferramentas de investigação e edição para o agente. Busca
textual continua sendo feita com `rg`; análise semântica e refactors maiores
podem usar LSP/AST sob demanda conforme a
[ADR-003](decisions/adr-003-on-demand-semantic-code-tooling.md).

| Categoria | Ferramentas |
|---|---|
| Busca e shell | `ripgrep`, `jq`, `git`, `gh`, `az` |
| TypeScript/JavaScript | `typescript-language-server`, `tsserver`, `tsc`, `ts-morph` |
| Python | `pyright`, `basedpyright`, `ruff`, `libcst` |
| AST multi-linguagem | `ast-grep`, `tree-sitter` |

### Comandos slash no chat

O chat web expoe comandos `/` por um contrato do CappyCloud, nao por parsing
livre no frontend. A UI consulta `GET /api/conversations/{id}/commands`,
renderiza comandos descobertos do runtime e envia execucoes para
`POST /api/conversations/{id}/commands/execute`.

Regras de fronteira:

1. Regras de disponibilidade, autorizacao, confirmacao e execucao ficam em
   `services/api/app/application/use_cases/chat_commands.py` e
   `services/api/app/application/use_cases/chat_command_execution.py`.
2. O acesso ao runtime usa `ChatCommandRuntimePort` em
   `services/api/app/ports/chat_commands.py`, com adapter real em
   `services/api/app/adapters/secondary/sandbox_runtime/chat_commands.py`.
3. Modelos mostrados por `/model` usam o catalogo autorizado do CappyCloud; o
   OpenClaude nao vira fonte de verdade para modelo, permissao, historico,
   tokens ou custo.
4. Comandos upstream sem caminho headless seguro continuam descobriveis, mas
   aparecem indisponiveis com motivo em portugues.
### Evento ActionRequired

Quando o openclaude precisa de confirmação humana, ele emite `ActionRequired` via gRPC.
O `GrpcSession` pausa o stream, expõe o `PendingAction` para o frontend e retoma
quando o usuário responde via `send_input()`.

## Integrações Externas

| Serviço | Uso |
|---|---|
| PostgreSQL | Usuários, conversas, sessões de agente |
| Redis | Cache de sessões com TTL |
| Docker | Sandboxes que hospedam openclaude, session_server e worktrees |
| OpenRouter | Gateway LLM (modelo dinâmico por conversa, com `.env` apenas como fallback) |
| openclaude gRPC | Servidor de agente dentro do container (porta 50051) |

## Comandos

```bash
cd services/api

# Instalar dependências de dev
pip install -r requirements.txt -e ".[dev]"

# Lint
ruff check .
ruff format --check .

# Type check
mypy app/

# Testes + cobertura
pytest

# Pre-commit (todos os arquivos)
pre-commit run --all-files
```
