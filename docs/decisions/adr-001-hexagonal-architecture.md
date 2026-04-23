# ADR-001 — Arquitetura Hexagonal (Ports & Adapters)

**Status:** Aceite
**Data:** 2024
**Contexto:** CappyCloud — plataforma de agentes IA

---

## Contexto

O CappyCloud precisa de:
- **Múltiplos adaptadores de entrada** (HTTP, potencialmente CLI, WebSocket)
- **Múltiplos adaptadores de saída** (PostgreSQL, Redis, Docker, gRPC, OpenRouter)
- **Testes rápidos e isolados** sem dependência de containers ou rede
- **Substituição de dependências** sem alterar lógica de negócio (ex.: trocar
  SQLAlchemy por outro ORM, ou trocar OpenRouter por outro provider de LLM)

O modelo CRUD tradicional (lógica nos routers/views) torna os testes lentos e
acoplados à infraestrutura, e dificulta substituições.

---

## Decisão

Adotar **Arquitetura Hexagonal (Ports & Adapters)** com as seguintes camadas:

```
Primary Adapters (HTTP routers)
        ↓ chamam use cases
Application Layer (use cases)
        ↓ usam ports (ABCs)
Ports (interfaces)
        ↓ implementadas por
Secondary Adapters (SQLAlchemy, gRPC, Docker)
```

### Regras derivadas

1. **Toda lógica de negócio** vive em `app/application/use_cases/`
2. **HTTP routers** só fazem parse de request, chamam use case, retornam response
3. **Ports** são ABCs em `app/ports/` — definem contratos sem implementação
4. **Cada port** tem: adapter real (`app/adapters/secondary/`) + fake em memória
   (`tests/conftest.py`)
5. **Domain** (`app/domain/`) tem zero dependências externas — stdlib Python apenas

---

## Consequências

### Positivas

- **Testes unitários rápidos:** use cases testados com fakes em memória, sem DB,
  sem Docker, sem rede. Suite completa roda em segundos.
- **LSP garantido:** fakes e adapters reais implementam o mesmo ABC — testes de
  contrato em `tests/adapter/` verificam ambos com as mesmas asserções.
- **Independência de framework:** lógica de negócio não importa FastAPI nem
  SQLAlchemy — pode ser reutilizada em outros contextos.
- **Substituição segura:** trocar PostgreSQL por outro banco, ou OpenRouter por
  outro LLM, só exige criar um novo adapter secundário.

### Negativas / Trade-offs

- **Mais arquivos:** cada feature exige entidade + port + adapter + use case +
  schema. Para CRUDs simples pode parecer verbose.
- **Curva de aprendizado:** desenvolvedores acostumados com Django/Rails precisam
  internalizar a separação de camadas.
- **Wiring manual:** as dependências são injetadas em `deps.py` — sem container
  de DI automático (escolha deliberada para manter clareza).

---

## Alternativas consideradas

### MVC / Active Record (Django-style)
Rejeitado: lógica nos models/views dificulta testes unitários e troca de
adaptadores. Testes precisariam de banco de dados real.

### Clean Architecture (Uncle Bob)
Considerado: overlapping com Hexagonal. Optamos pela nomenclatura Hexagonal por
ser mais direta e conhecida na comunidade Python/FastAPI.

### CQRS + Event Sourcing
Considerado para futuro se o domínio crescer significativamente. Não justificado
na complexidade atual.

---

## Referências

- `services/api/app/domain/` — entidades e value objects
- `services/api/app/ports/` — ABCs de repositórios e serviços
- `services/api/app/application/use_cases/` — lógica de negócio
- `services/api/app/adapters/` — primary (HTTP) e secondary (SQLAlchemy, etc.)
- `docs/ARCHITECTURE.md` — diagrama e mapa de diretórios
- `docs/AGENT_RULES.md` — regras de desenvolvimento derivadas desta decisão
