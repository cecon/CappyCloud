---
name: create-migration
description: Use está habilidade quando precisar criar uma migration no CappyCloud, quando precisar alterar, adicionar, remover ou renomear tabelas, colunas ou qualquer alteração no banco de dados.
---

# Migrations com Alembic — CappyCloud

## Regra Fundamental

> **JAMAIS crie ou edite arquivos de migration manualmente.**
> Sempre use `alembic revision` para gerar o arquivo. O timestamp no nome garante a ordem.

---

## Setup inicial (apenas uma vez)

Se `services/api/alembic/` não existir:

```bash
cd services/api
alembic init alembic
```

Depois configure `alembic.ini` e `alembic/env.py`:

**`alembic.ini`** — aponte para o banco:
```ini
sqlalchemy.url = postgresql+asyncpg://user:pass@localhost/cappycloud
```
> Em produção, prefira ler da variável de ambiente em `env.py` em vez de hardcodar aqui.

**`alembic/env.py`** — conecte os ORM models:
```python
from app.infrastructure.orm_models import Base
target_metadata = Base.metadata
```

Para banco async (asyncpg), use `run_async_migrations`:
```python
from sqlalchemy.ext.asyncio import async_engine_from_config

async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
```

Adicione `alembic` ao `requirements.txt`:
```
alembic>=1.13.0
```

---

## Criar uma nova migration

### Autogenerate (preferido)

Detecta automaticamente diferenças entre os ORM models e o banco:

```bash
cd services/api
alembic revision --autogenerate -m "descricao_curta_do_que_muda"
```

Exemplo:
```bash
alembic revision --autogenerate -m "add_refresh_token_to_users"
```

Arquivo gerado: `alembic/versions/20260415_143022_add_refresh_token_to_users.py`

O timestamp `YYYYMMDD_HHMMSS` é gerado automaticamente e **garante a ordem de execução**.

### Migration vazia (para DDL manual ou dados)

```bash
alembic revision -m "seed_default_roles"
```

Preencha manualmente as funções `upgrade()` e `downgrade()` no arquivo gerado.

---

## Estrutura do arquivo gerado

```python
"""add_refresh_token_to_users

Revision ID: a1b2c3d4e5f6
Revises: <id_da_anterior>
Create Date: 2026-04-15 14:30:22.123456
"""
from alembic import op
import sqlalchemy as sa

def upgrade() -> None:
    op.add_column("users", sa.Column("refresh_token", sa.String(), nullable=True))

def downgrade() -> None:
    op.drop_column("users", "refresh_token")
```

**Sempre revise o arquivo gerado antes de aplicar** — o autogenerate pode não detectar:
- Renomeações de coluna (aparece como drop + add)
- Constraints complexas
- Indexes condicionais

---

## Aplicar migrations

```bash
# Subir para a versão mais recente
alembic upgrade head

# Subir N versões
alembic upgrade +1

# Ver versão atual
alembic current

# Ver histórico
alembic history --verbose
```

## Reverter migrations

```bash
# Voltar uma versão
alembic downgrade -1

# Voltar para revisão específica
alembic downgrade a1b2c3d4e5f6

# Voltar tudo (cuidado em produção!)
alembic downgrade base
```

---

## Checklist antes de cada migration

- [ ] ORM model em `app/infrastructure/orm_models.py` atualizado
- [ ] Migration gerada com `alembic revision --autogenerate`
- [ ] Arquivo gerado revisado (upgrade + downgrade corretos)
- [ ] `alembic upgrade head` executado localmente
- [ ] Testes passando (`pytest`)

---

## Boas práticas

| Faça | Evite |
|------|-------|
| Nome descritivo em snake_case | Nomes genéricos como `update_db` |
| Sempre implementar `downgrade()` | Deixar `downgrade()` vazio |
| Uma mudança lógica por migration | Misturar alterações não relacionadas |
| Commitar migration junto com o model | Commitar model sem migration |
