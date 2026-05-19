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

### 6.1 Mutation Testing

Cobertura de linhas é necessária mas insuficiente. Um teste que executa
uma linha sem afirmar nada específico sobre o comportamento é um falso
positivo: a IA pode gerar `assert resultado is not None` e bater 95% de
coverage com testes que não garantem nada.

Para regras de negócio, autorização, cálculo, state machines e
propagação de contexto crítico (ex.: `confluence_url`, `confluence_space`,
custo, branch resolution), escreva testes que **matem mutantes**:

- Asserts **sobre o valor**, não sobre tipo/existência:
  ✗ `assert isinstance(repo, dict)`
  ✓ `assert repo["confluence_space"] == "FRONTEND"`
- Cobrir **fronteira explicitamente**: limite, +1, -1, string vazia,
  whitespace puro, lista vazia, lista com 1 item.
- Para cada condicional, **ambos os ramos** + um teste exatamente no
  threshold (`==`, não só `<` e `>`).
- Evitar snapshot inteiro como única validação — preferir asserts pontuais
  por propriedade.

#### Quando rodar mutmut

- **Não roda no CI por padrão** (10–100× mais lento; gera mutantes
  equivalentes que viram ruído).
- Rodar **localmente** ao tocar nos módulos críticos listados em
  `[tool.mutmut].paths_to_mutate` (`services/api/pyproject.toml`).
- Score alvo informal: **≥ 80%** nos arquivos críticos. Mutantes
  sobreviventes devem ser inspecionados — ou se transformam em teste novo,
  ou viram comentário justificando equivalência.

#### Comandos

```bash
cd services/api
pip install -e '.[dev]'
mutmut run                       # roda contra paths_to_mutate
mutmut results                   # lista sobreviventes
mutmut show <id>                 # vê o diff do mutante #<id>
mutmut show all                  # vê todos os sobreviventes
```

Foco mutmut em **regra de negócio**. Não usar em DTOs Pydantic, HTTP
adapters triviais (parse → call → return) ou wrappers de SDK externo —
custo > benefício.

## 7. DRY & KISS

- Lógica de validação vive em `app/domain/value_objects.py`. Validators Pydantic
  delegam para essas funções — nunca duplicar a regra.
- Sem abstrações auxiliares para operações únicas.
- Três linhas similares são melhores que uma abstração prematura.

## 8. Controles de Engenharia

- **Guides (feedforward)**: ruff + mypy rodam no CI e no pre-commit.
- **Sensors (feedback)**: pytest-cov com `--cov-fail-under=80` como gate no CI.
- CI vermelho = PR bloqueado. Corrigir antes de fazer merge.
