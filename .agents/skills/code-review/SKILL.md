---
name: code-review
description: Realiza revisão de código técnica, usar está habilidade quando precisar fazer revisão de código, verificar conformidade com padrões arquiteturais (Hexagonal), qualidade de código, performance e corretude lógica.
---

# Code Review — CappyCloud

Este guia define o processo e os critérios para revisão de código no projeto CappyCloud. Toda alteração deve ser revisada seguindo estes padrões rigorosos.

## Checklist de Revisão

### 1. Arquitetura Hexagonal (Ports & Adapters)
- [ ] **Lógica de Negócio**: TODA a lógica de negócio está em `app/application/use_cases/`?
- [ ] **Adapters Primários**: Os routers em `app/adapters/primary/http/` são "thin"? Eles apenas fazem parse, chamam o use case e retornam a resposta?
- [ ] **Ports**: Novas dependências externas (DB, serviços) possuem uma Interface (ABC) em `app/ports/`?
- [ ] **Adapters Secundários**: As implementações concretas estão em `app/adapters/secondary/`?
- [ ] **Domínio**: As entidades em `app/domain/` são puras (sem dependências externas como SQLAlchemy ou FastAPI)?

### 2. Padrões de Código e Qualidade
- [ ] **Limite de Linhas**: O arquivo possui mais de 300 linhas? Se sim, deve ser dividido.
- [ ] **Tipagem**: Todas as funções e classes públicas possuem type annotations (`mypy` compliant)?
- [ ] **Nomenclatura**: Segue `snake_case` para Python e `camelCase` para TypeScript?
- [ ] **Validação**: Validações de domínio vivem no `domain` (value objects) e são chamadas pelos schemas Pydantic?
- [ ] **Tratamento de Erros**: Exceções de domínio são capturadas e mapeadas para erros HTTP adequados nos adapters primários?

### 3. Testes e Cobertura
- [ ] **Unitários**: Novos use cases possuem testes unitários usando fakes em `tests/unit/`?
- [ ] **Contrato**: Novos adapters possuem testes de contrato parametrizados em `tests/adapter/`?
- [ ] **Integração**: Alterações em rotas possuem testes de integração em `tests/integration/`?
- [ ] **Cobertura**: A cobertura de testes permanece ≥ 80%?

### 4. Performance e Escalabilidade
- [ ] **Async/Await**: Todas as operações de I/O (DB, Redis, gRPC) utilizam `async/await`?
- [ ] **N+1 Queries**: O uso de SQLAlchemy evita o problema de N+1 queries (ex: usando `selectinload` ou `joinedload`)?
- [ ] **Redis**: Cache e sessões estão sendo geridos corretamente com TTL?

## Guia de Feedback

| Tipo de Comentário | Abordagem |
|-------------------|-----------|
| **Crítico (Blocking)** | Use quando violar regras de `ARCHITECTURE.md` ou `AGENT_RULES.md`. |
| **Sugestão (Non-blocking)** | Use para melhorias de legibilidade ou refatoração opcional. |
| **Dúvida** | Use quando a intenção do código não estiver clara. |

## Padrões de Import
- **Backend**: Use caminhos absolutos baseados na raiz `app/` (ex: `from app.domain.entities import ...`).
- **Frontend**: Use aliases configurados se disponíveis, caso contrário, caminhos relativos consistentes.

---
**Nota**: O código é a fonte da verdade. Se houver divergência entre este guia e o código estável bem-sucedido, questione a documentação.
