---
name: service-implementation
description: Use esta habilidade quando precisar implementar novas funcionalidades nos serviços de backend (API, Agente, CLI, Pipelines) seguindo os padrões arquiteturais específicos de cada componente do CappyCloud.
---

# Service Implementation — CappyCloud (Backend Focus)

Este guia define os padrões de implementação para os diferentes serviços contidos em `services/*`. Siga o padrão correspondente ao componente que está modificando.

## 1. Backend API (`services/api`) — Arquitetura Hexagonal

O fluxo obrigatório para novas funcionalidades segue 6 passos:

1.  **Domínio** (`app/domain/entities.py`): Defina a entidade pura (dataclass). Sem dependências externas.
2.  **Port** (`app/ports/`): Defina o contrato (ABC) para Repositórios ou Serviços Externos.
3.  **Adapter Secundário** (`app/adapters/secondary/`): Implemente a Port (ex: SQLAlchemy para DB, gRPC para Agente).
4.  **Use Case** (`app/application/use_cases/`): Implemente a lógica em uma classe com método `execute()`. Deve receber apenas Ports no `__init__`.
5.  **DI Wiring** (`app/adapters/primary/http/deps.py`): Registre o Use Case e seus Adapters no sistema `Depends()` do FastAPI.
6.  **Router** (`app/adapters/primary/http/`): Endpoint "thin" que injeta o Use Case e retorna o Schema Pydantic.

**Regra de Ouro**: Máximo 300 linhas por arquivo. Lógica de validação rica deve viver no `Domain` (Value Objects).

## 2. Agente e Pipelines (`services/cappycloud_agent` & `services/pipelines`)

Utiliza um padrão de **Dispatcher/Runner** desacoplado do ciclo de vida HTTP.

- **Entry Point**: Classe `Pipeline` com sistema de `Valves` (Pydantic) para configuração via env vars.
- **Bridge Sync/Async**: Como o `pipe()` é frequentemente chamado por frameworks síncronos, use `asyncio.run_coroutine_threadsafe(coro, self._loop)` para disparar lógica async.
- **Task Dispatcher**: Novos comportamentos do agente devem ser integrados via `_task_dispatcher.py`.
- **Event Streaming**: O estado do agente é persistido na tabela `agent_events`. O streaming para o frontend é feito via polling SSE baseado em cursores (`last_id`).
- **Módulos Privados**: Use o prefixo `_` para componentes internos (`_grpc_session.py`, `_session_store.py`) que não devem ser expostos fora do pacote.

## 3. CLI (`services/cli`) — Typer

Interface de linha de comando para gestão e automação.

- **Estrutura**: `app` principal em `cappy/main.py` que agrega sub-apps via `app.add_typer()`.
- **Comandos**: Organize comandos por domínio em arquivos privados (ex: `cappy/_task_cmds.py`).
- **Comunicação**: Use `httpx.Client` com `base_url` e headers de autenticação (`Bearer token`) para falar com a API.
- **Configuração**: Persistência de estado local (tokens/urls) em `~/.cappy/config.json`.

## 4. Sandbox e Ambiente (`services/sandbox`)

Define o runtime onde o agente executa o código do usuário.

- **Isolamento**: Um container Docker por usuário (identificado por `user_id`).
- **Contexto**: Uso intensivo de `git worktrees` em `/repos/sessions/{conv_id}/{alias}` para isolar conversas sem clonar o repo múltiplas vezes.
- **Comunicação**: O agente dentro do sandbox expõe um servidor gRPC na porta `50051`. A API comunica-se com ele através do `PipelineAdapter`.

## Padrões Transversais

- **Async/Await**: Obrigatório em todo I/O (DB, Redis, gRPC, HTTP).
- **Naming**: `snake_case` para Python. Use nomes de classes que descrevam a ação para Use Cases (ex: `SyncRepository`, `CancelConversation`).
- **Tratamento de Erros**:
    - Backend: Capture exceções de domínio e lance `HTTPException` no adapter primário.
    - CLI: Use `typer.Exit(1)` para erros fatais e `typer.echo(err=True)` para mensagens de erro.
- **Logs**: Use o logger padrão do Python configurado no nível do módulo (`log = logging.getLogger(__name__)`).

## 6. Ativação de Skills de Qualidade
Ao finalizar qualquer implementação em `services/*`, você **DEVE** ativar as seguintes habilidades para garantir a integridade do código:
1.  **code-review**: Para validar a aderência à Arquitetura Hexagonal e padrões de código.
2.  **vulnerability-auditor**: Para auditar possíveis falhas de segurança ou exposição de dados.

