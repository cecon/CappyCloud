---
name: prepare-pr
description: Receita de bolo para preparar um Pull Request no CappyCloud sem quebrar o CI. Use ANTES de fazer git push de uma branch nova ou quando o usuário pedir para abrir um PR, criar pull request, "vamos fazer o pr", ou quando os checks do GitHub Actions (API CI, Pre-commit) estiverem vermelhos.
---

# Preparar PR no CappyCloud

CI do repo é estrito. Rodar lint/format/mypy/pytest **antes** do push poupa 2-4 ciclos de "push → CI vermelho → fix → push".

## Workflow obrigatório

Copie esta checklist e marque cada item:

```
- [ ] 1. ruff check  (services/api)
- [ ] 2. ruff format --check  (services/api)
- [ ] 3. mypy app/  (no container, Python 3.14)
- [ ] 4. pytest  (no container, com env vars)
- [ ] 5. Commit + push
- [ ] 6. gh pr create
- [ ] 7. gh pr checks → confirmar verde
```

Cada passo abaixo tem o comando exato + a armadilha conhecida.

---

## 1. Ruff lint

**Comando exato:**

```bash
cd /Users/eduardomendonca/projetos/CappyCloud/services/api
ruff check .
```

**Armadilha 1 — Python local é 3.9 (não roda o `pip install -e .[dev]`):**

Crie um venv só para o `ruff`. Não precisa instalar o projeto:

```bash
python3 -m venv /tmp/cci_venv
/tmp/cci_venv/bin/pip install --upgrade pip
/tmp/cci_venv/bin/pip install ruff
/tmp/cci_venv/bin/ruff --version  # deve ser >= 0.6
```

Depois use `/tmp/cci_venv/bin/ruff` em vez de `ruff`.

**Armadilha 2 — Sempre instale a versão mais nova do `ruff`.** O CI usa `ruff>=0.6` no `pyproject.toml`, mas o GitHub Actions instala a última disponível, que tem regras novas (ex.: `RUF059` — "Unpacked variable never used"). Se você rodar `ruff` 0.6.9 local, ele **não pega** o que o CI pega.

```bash
/tmp/cci_venv/bin/pip install --upgrade ruff
```

**Armadilha 3 — `working_directory` da Shell tool não muda o `pwd` de verdade.** Sempre use `cd services/api && ruff check .` em vez de confiar no parâmetro `working_directory`.

**Erros típicos e fix:**

- `RUF059 Unpacked variable 'foo' is never used` → renomeie para `_foo`.
- `F401 'x' imported but unused` → remova o import.

---

## 2. Ruff format check

```bash
cd services/api && /tmp/cci_venv/bin/ruff format --check .
```

Se falhar, **rode o format e revalide o lint** (format pode introduzir erros novos):

```bash
cd services/api && /tmp/cci_venv/bin/ruff format .
cd services/api && /tmp/cci_venv/bin/ruff check .
```

**Armadilha — chamadas longas com argumentos posicionais:** `ruff format` quebra `f("a","b","c","d","e")` em uma linha por argumento se a linha estourar 100 chars. Não tente "minimizar" linhas manualmente — só rode o `format` e aceite o que ele decidir.

---

## 3. Mypy + Pytest (no container `cappycloud-api`)

O Python local é 3.9 e o projeto requer 3.14. Use o container que já está rodando:

```bash
# 1) Garante deps de teste no container
docker exec cappycloud-api pip install -q \
  "ruff" "mypy" "pytest>=8.3,<9" "pytest-asyncio>=0.24,<1" \
  pytest-cov httpx aiosqlite types-passlib

# 2) Copia código e config atualizados (a imagem está build-ada com snapshot antigo)
docker cp services/api/app cappycloud-api:/app/
docker cp services/api/tests cappycloud-api:/app/tests
docker cp services/api/pyproject.toml cappycloud-api:/app/pyproject.toml
docker cp services/api/alembic cappycloud-api:/app/alembic
docker cp services/api/alembic.ini cappycloud-api:/app/alembic.ini

# 3) Mypy
docker exec -w /app cappycloud-api mypy app/

# 4) Pytest com env vars que o CI usa
docker exec -w /app \
  -e DATABASE_URL="sqlite+aiosqlite:///:memory:" \
  -e JWT_SECRET="test-secret-ci" \
  -e APP_NAME="CappyCloud Test" \
  cappycloud-api pytest
```

**Armadilha — pytest-asyncio precisa do `pyproject.toml` no cwd.** Sem ele, todos os testes async falham com "async functions are not natively supported". Por isso o `docker cp services/api/pyproject.toml cappycloud-api:/app/pyproject.toml` acima.

**Armadilha — versão do pytest.** Se o container tiver `pytest 9.x`, fixtures async quebram. O CI usa `pytest>=8.3` que na prática resolve para 8.x. Force `pytest>=8.3,<9` no `pip install`.

**Cobertura:** `pytest` tem gate `--cov-fail-under=80`. Se quebrar abaixo de 80%, ou adicione testes ou marque o arquivo em `[tool.coverage.run] omit` no `pyproject.toml` (com justificativa no commit).

---

## 4. Pre-commit (espelha o CI `Pre-commit (changed files)`)

O CI roda `pre-commit run --from-ref origin/main --to-ref HEAD`. Hooks ativos:

- `ruff` (autofix)
- `ruff-format`
- `end-of-file-fixer`
- `trailing-whitespace`
- `check-yaml`
- `check-merge-conflict`
- `check-added-large-files` (--maxkb=500)
- `max-file-length` (≤ 300 linhas, exclude `^web/`)

**Armadilha conhecida — patches `.patch`.** O `trailing-whitespace` e `end-of-file-fixer` quebram unified diffs (linhas de contexto vazias terminam com 1 espaço, que é parte do formato `diff`). Já temos `exclude: \.patch$` no `.pre-commit-config.yaml` para os 2 hooks. **Não adicione novos hooks que tocam patches sem esse exclude.**

**Armadilha — arquivo > 300 linhas.** O hook `max-file-length` (script `scripts/check_file_length.py`) bloqueia. Se um arquivo passar de 300 linhas, refatore em sub-arquivos. Esse limite vem das regras do projeto ([docs/AGENT_RULES.md](../../docs/AGENT_RULES.md)).

---

## 5. Commit + push

Use HEREDOC para a mensagem (preserva quebras):

```bash
git checkout -b feat/<nome-curto>
git add <arquivos>
git commit -m "$(cat <<'EOF'
tipo(scope): titulo curto em minusculas

Detalhes em portugues, sem acentos no titulo.
Cada paragrafo aqui explica o "porque", nao o "o que".
EOF
)"
git push -u origin HEAD
```

**Convenção de mensagens** (vista no histórico do repo):

- `feat(scope):` — funcionalidade nova
- `fix(scope):` — correção de bug
- `fix(ci):` — apenas para satisfazer lint/format/CI sem mudança funcional
- `refactor(scope):` — reorganização sem mudar comportamento

Scopes comuns: `api`, `sandbox`, `agent`, `code-indexer`, `frontend`, `ci`.

**Nunca** `--amend` se a branch já está no remote — crie um novo commit.

---

## 6. Abrir o PR

```bash
gh pr create --title "tipo(scope): titulo" --body "$(cat <<'EOF'
## Summary

- Bullet 1: o que mudou e por que.
- Bullet 2: efeito colateral relevante.

## Test plan

- [ ] Item testavel 1
- [ ] Item testavel 2

EOF
)"
```

---

## 7. Confirmar checks verdes

```bash
sleep 30  # da tempo do CI registrar
gh pr checks <numero>
```

Se algo falhar:

```bash
gh run view <run-id> --log-failed | tail -60
```

Corrija, commite (sem `--amend`), `git push`, e repita.

---

## Pegadinhas globais já vividas

Quando bater alguma destas mensagens, o fix é conhecido — não fique investigando:

| Mensagem do CI | Causa | Fix |
|---|---|---|
| `RUF059 Unpacked variable 'X' is never used` | Tupla unpacked sem uso | Prefixe com `_X` |
| `F401 'X' imported but unused` | Import morto | Remova |
| `Would reformat: app/...py` | Format quebra args longos em multilinha | Rode `ruff format .` |
| `trailing-whitespace ... Fixing services/.../*.patch` | Hook quebra unified diff | Confirme `exclude: \.patch$` no `.pre-commit-config.yaml` |
| `async functions are not natively supported` | `pyproject.toml` não está no cwd OU pytest 9.x | `docker cp` o pyproject + downgrade pytest |
| `Required test coverage of 80% not reached` | Coverage < 80% | Add testes ou inclua em `[tool.coverage.run] omit` |
| `column conversations.X does not exist` | Migration faltando | Use a skill `create-migration` |

---

## Atalho: tudo de uma vez

Quando já estiver familiarizado, rode este script mental:

```bash
# Lint + format
cd services/api && /tmp/cci_venv/bin/ruff check . && /tmp/cci_venv/bin/ruff format --check .

# Mypy + tests no container
docker cp services/api/app cappycloud-api:/app/ && \
docker cp services/api/tests cappycloud-api:/app/tests && \
docker cp services/api/pyproject.toml cappycloud-api:/app/pyproject.toml && \
docker exec -w /app cappycloud-api mypy app/ && \
docker exec -w /app \
  -e DATABASE_URL="sqlite+aiosqlite:///:memory:" \
  -e JWT_SECRET="test-secret-ci" \
  -e APP_NAME="CappyCloud Test" \
  cappycloud-api pytest
```

Se tudo verde → `git commit && git push && gh pr create`.
