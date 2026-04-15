# CappyCloud — Architecture Guide for Claude Code

## Project Overview

CappyCloud is an AI agent platform: FastAPI backend + React frontend + sandboxed
openclaude agents running in isolated containers (one per user) with git worktrees per
conversation.

## Architecture: Hexagonal (Ports & Adapters)

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

## Mandatory Rules

### 1. Business Logic Location
- **ALL** business logic lives in `app/application/use_cases/`.
- HTTP routers (`app/adapters/primary/http/`) may ONLY: parse requests, call one use
  case, return responses. No `SELECT`, no `INSERT`, no domain logic.

### 2. Ports & Adapters
- Every external dependency (DB, agent, token service) is accessed through a **Port**
  (ABC in `app/ports/`).
- Every new port MUST have:
  - One real adapter in `app/adapters/secondary/`
  - One in-memory fake in `tests/conftest.py`

### 3. Liskov Substitution Principle (LSP)
- In-memory fakes MUST implement the same ABC as real adapters.
- Add parametrized contract tests in `tests/adapter/` that run the same assertions
  against all implementations of each port.

### 4. File Size
- **Maximum 300 lines per file**. Split by single responsibility if exceeded.

### 5. Type Annotations
- All public functions and classes MUST have type annotations.
- Run `mypy app/` before committing. Zero errors required.

### 6. Testing & Coverage
- Coverage must stay **≥ 80%** (`pytest --cov` enforces this).
- Unit tests use only in-memory fakes (no DB, no network).
- Integration tests use `httpx.AsyncClient` + `app.dependency_overrides`.
- Run `pytest` before pushing.

### 7. DRY & KISS
- Validation logic lives in `app/domain/value_objects.py`. Pydantic validators
  delegate to those functions — never duplicate the rule.
- No helper abstractions for one-time operations.
- Three similar lines are better than a premature abstraction.

### 8. Harness Engineering Controls
- **Guides (feedforward)**: ruff + mypy run in CI and pre-commit.
- **Sensors (feedback)**: pytest-cov with `--cov-fail-under=80` gate in CI.
- A red CI = blocked PR. Fix before merging.

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
```

## Commands

```bash
cd services/api

# Install dev dependencies
pip install -r requirements.txt -e ".[dev]"

# Lint
ruff check .
ruff format --check .

# Type check
mypy app/

# Tests + coverage
pytest

# Pre-commit (all files)
pre-commit run --all-files
```

## Agent Architecture

The agent layer (`services/cappycloud_agent/`) uses:
- **EnvironmentManager**: one persistent Docker container per user with a shared
  openclaude gRPC server (port 50051)
- **Git worktrees**: one per `(user_id, conversation_id)` inside the container
- **GrpcSession**: persistent bidirectional stream; pauses on `ActionRequired` events,
  resumes when user replies

The `PipelineAdapter` in `app/adapters/secondary/agent/` wraps the `Pipeline` class
and satisfies the `AgentPort` ABC — routers and use cases never import `Pipeline`
directly.
