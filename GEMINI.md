# CappyCloud — Contexto de Agente IA

Documentação técnica otimizada para consumo por agentes de IA (Gemini CLI).

## 1. Visão Geral do Projeto
CappyCloud é uma plataforma de agentes de IA focada em engenharia de software assistida. O sistema orquestra agentes que rodam em containers Docker isolados (Sandboxes), utilizando **git worktrees** para isolar o contexto de cada conversa.

- **Problema resolvido**: Execução segura e isolada de agentes de IA com acesso ao sistema de arquivos e ferramentas de execução (shell, git, browser).
- **Stack Principal**:
    - **Backend**: Python 3.14+ (FastAPI).
    - **Frontend**: React 19 (Vite + TypeScript).
    - **Agente**: Integração com `openclaude` via gRPC.
- **Dependências Críticas**:
    - **Python**: `fastapi`, `sqlalchemy` (async), `alembic`, `redis`, `docker`, `grpcio`, `apscheduler`.
    - **Frontend**: `react`, `@mantine/core` (UI), `react-router-dom`, `react-markdown`.
    - **Infra**: `postgres` (pgvector), `redis`, `docker`.

## 2. Arquitetura e Estrutura de Pastas
O projeto utiliza **Arquitetura Hexagonal (Ports & Adapters)** no backend para garantir o desacoplamento da lógica de negócio.

### Mapa de Diretórios
- `/services/api/app/`: Núcleo do Backend.
    - `domain/`: Entidades puras e objetos de valor (sem dependências externas).
    - `ports/`: Interfaces (ABCs) para repositórios e serviços externos.
    - `application/use_cases/`: Lógica de negócio e orquestração.
    - `adapters/`: Implementações concretas.
        - `primary/http/`: Routers FastAPI e esquemas Pydantic.
        - `secondary/`: Implementações de persistência (SQLAlchemy), gRPC e segurança.
    - `infrastructure/`: Configurações de ORM, DB, e segurança.
- `/services/cappycloud_agent/`: Lógica de orquestração do agente (Pipeline, Docker Manager, gRPC Session).
- `/services/sandbox/`: Definição da imagem Docker onde o agente executa.
- `/web/src/`: Frontend React.
    - `pages/`: Componentes de página (Chat, Settings, Environments).
    - `components/`: Componentes reutilizáveis.
    - `api.ts`: Cliente HTTP centralizado com tratamento de erros.
- `/proto/`: Definições gRPC (`openclaude.proto`).

### Fluxo de Requisição
1. **Frontend** envia comando via HTTP/SSE.
2. **FastAPI Router** (`primary adapter`) valida entrada com Pydantic.
3. **Use Case** (`application`) orquestra a ação.
4. **Pipeline** (`agent adapter`) garante que o container Docker do usuário está ativo.
5. **GrpcSession** envia o comando para o container via gRPC.
6. **Resposta** é transmitida via SSE (Server-Sent Events) para o frontend.

## 3. Setup Local
- **Pré-requisitos**: Docker, Node.js (pnpm), Python 3.14.
- **Comandos**:
    - `docker compose up -d`: Sobe Infra (Postgres, Redis, Sandbox) e API.
    - `cd web && pnpm install && pnpm dev`: Inicia frontend.
    - `cd services/api && alembic upgrade head`: Roda migrações.
- **Testes**: `pytest` (backend), `pnpm lint` (frontend).
- **Variáveis de Ambiente Obrigatórias**:
    - `OPENROUTER_API_KEY`: Chave para LLM.
    - `DATABASE_URL`: String de conexão Postgres.
    - `JWT_SECRET`: Chave para autenticação.

## 4. Padrões de Código e Convenções
- **Nomenclatura**: `snake_case` (Python), `camelCase` (TypeScript/JS), `PascalCase` (Componentes/Classes).
- **Tratamento de Erros**:
    - **Backend**: Exceções customizadas no `domain`, mapeadas para `HTTPException` nos adapters primários.
    - **Frontend**: Classe `AuthError` para 401, `formatApiErrorPayload` para erros de validação (422).
- **Validação de Dados**:
    - **Backend**: Pydantic v2 (`schemas.py`).
    - **Frontend**: Mantine Form + Zod (ou validações manuais em `validation.ts`).
- **Resposta da API**: JSON padrão. Fluxos de longa duração (chat) usam **SSE** com prefixo `data:`.
- **Imports**: Caminhos absolutos/aliases configurados via `tsconfig.json` e `pyproject.toml`.
- **Async**: Uso mandatório de `async/await` em IO (DB, gRPC, API).

## ⚠️ Pontos de Atenção
- **Gerenciamento de Sandbox**: O ciclo de vida dos containers Docker é atrelado ao `user_id`. Ociosidade é gerida pelo `SANDBOX_IDLE_TIMEOUT`.
- **Git Worktrees**: Cada conversa cria um worktree físico no volume do sandbox. Falhas no clone/checkout travam o chat.
- **gRPC Stream**: O stream gRPC é persistente por sessão. Se o container reiniciar, a sessão gRPC deve ser restabelecida.
- **Dívida Técnica**: O `pyproject.toml` lista dependências vazias, confiando no `requirements.txt` para o runtime.
- **Ambiguidade**: `web/src/api.ts` contém lógica de UI misturada com chamadas de rede (ex: `formatApiErrorPayload`).
```markdown
