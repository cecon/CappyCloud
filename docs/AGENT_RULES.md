# CappyCloud — Regras de Desenvolvimento

Regras obrigatórias para todos os contribuidores. O CI bloqueia PRs que violem
qualquer uma dessas regras.

## 1. Business Logic Location

- **TODA** lógica de negócio vive em `app/application/use_cases/`.
- HTTP routers (`app/adapters/primary/http/`) podem APENAS: parsear requests,
  chamar um use case, retornar responses. Proibido `SELECT`, `INSERT` ou
  qualquer lógica de domínio diretamente no router.

## 2. Ports & Adapters

- Toda dependência externa (DB, agente, serviço de token) é acessada através de
  uma **Port** (ABC em `app/ports/`).
- Toda nova port DEVE ter:
  - Um adapter real em `app/adapters/secondary/`
  - Um fake em memória em `tests/conftest.py`

## 3. Princípio de Substituição de Liskov (LSP)

- Fakes em memória DEVEM implementar o mesmo ABC que os adapters reais.
- Adicionar testes de contrato parametrizados em `tests/adapter/` que rodam as
  mesmas asserções contra todas as implementações de cada port.

## 4. Tamanho de Arquivo

- **Máximo 300 linhas por arquivo de código**. Dividir por responsabilidade única se
  exceder. Arquivos Markdown (`.md`, `.mdx`, `.markdown`) ficam fora deste gate
  para permitir documentação técnica completa. Linhas em branco e linhas compostas
  apenas por comentário também não contam no limite.

## 5. Type Annotations

- Todas as funções e classes públicas DEVEM ter type annotations.
- Rodar `mypy app/` antes de commitar. Zero erros exigido.

## 6. Testes e Cobertura

- Cobertura deve permanecer **≥ 80%** (`pytest --cov` impõe isso).
- Testes unitários usam apenas fakes em memória (sem DB, sem rede).
- Testes de integração usam `httpx.AsyncClient` + `app.dependency_overrides`.
- Rodar `pytest` antes de fazer push.

## 7. DRY & KISS

- Lógica de validação vive em `app/domain/value_objects.py`. Validators Pydantic
  delegam para essas funções — nunca duplicar a regra.
- Sem abstrações auxiliares para operações únicas.
- Três linhas similares são melhores que uma abstração prematura.

## 8. Controles de Engenharia

- **Guides (feedforward)**: ruff + mypy rodam no CI e no pre-commit.
- **Sensors (feedback)**: pytest-cov com `--cov-fail-under=80` como gate no CI.
- CI vermelho = PR bloqueado. Corrigir antes de fazer merge.
