# Como executar os testes

Referência rápida para rodar a suite de testes do CappyCloud localmente.

---

## Setup inicial

```bash
cd services/api

# Instalar dependências (incluindo extras de dev)
pip install -r requirements.txt -e ".[dev]"
```

---

## Rodar tudo (modo padrão)

```bash
pytest
```

Inclui todos os testes + cobertura. O CI bloqueia PR se cobertura cair abaixo de 80%.

---

## Por camada

```bash
# Só testes unitários (use cases + domain — sem DB, sem rede)
pytest tests/unit/

# Só testes de contrato de adapters (LSP)
pytest tests/adapter/

# Só testes de integração (HTTP via httpx + dependency_overrides)
pytest tests/integration/
```

---

## Com relatório de cobertura

```bash
# Exibir no terminal
pytest --cov=app --cov-report=term-missing

# Gerar HTML (abre em browser depois)
pytest --cov=app --cov-report=html
open htmlcov/index.html
```

---

## Rodar um arquivo ou teste específico

```bash
# Arquivo
pytest tests/unit/test_auth.py

# Teste específico
pytest tests/unit/test_auth.py::test_register_user_success

# Por palavra-chave
pytest -k "register"
```

---

## Estrutura de testes

```
services/api/tests/
  conftest.py        ← Fakes em memória + fixtures compartilhadas
  unit/              ← Testam use cases + domain com fakes (sem I/O)
  adapter/           ← Testes de contrato LSP (mesmas asserções para fake e real)
  integration/       ← HTTP end-to-end via httpx.AsyncClient
```

**Regras:**
- Testes unitários: **apenas fakes** — nenhum acesso a DB ou rede
- Testes de integração: usam `app.dependency_overrides` + `aiosqlite` em memória
- Nunca mockar o que você não possui (use fakes que implementam o ABC)

---

## Pre-commit (todos os checks)

```bash
# Rodar todos os hooks no repositório inteiro
pre-commit run --all-files

# Ou só num arquivo
pre-commit run --files services/api/app/application/use_cases/auth.py
```

---

## Verificar tipo + lint separadamente

```bash
# Lint e formatação
ruff check .
ruff format --check .

# Type checking
mypy app/
```

---

## Checklist antes de abrir PR

- [ ] `pytest` passou (cobertura ≥ 80%)
- [ ] `mypy app/` sem erros
- [ ] `ruff check .` sem avisos
- [ ] `pre-commit run --all-files` passou
