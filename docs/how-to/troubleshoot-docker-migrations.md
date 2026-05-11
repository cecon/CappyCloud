# Post-mortem: Falhas de Inicialização do Docker e Migrations do Alembic

Este documento serve como registro dos problemas encontrados durante a inicialização dos containers Docker do CappyCloud (especificamente `cappycloud-postgres` e `cappycloud-api`) e como eles foram resolvidos.

## Resumo do Problema
Ao tentar subir o ambiente com `docker compose up -d` em um banco de dados limpo, o container do PostgreSQL ficava no estado `unhealthy` (crashando repetidamente) e a API falhava ao iniciar, abortando a execução com erros nas migrações do Alembic.

A falha ocorria em cascata devido a uma combinação de **conflitos entre scripts de inicialização crua no Postgres e o histórico das migrations do Alembic**.

## Sequência de Erros e Correções

### 1. Conflito no Entrypoint do Postgres (Unhealthy Container)
* **O Erro:** `dependency failed to start: container cappycloud-postgres is unhealthy`.
* **A Causa:** O `docker-compose.yml` montava a pasta `services/postgres/` diretamente em `/docker-entrypoint-initdb.d/`. Os arquivos `01-sandbox-multi-repo.sql` e `02-platform-control-plane.sql` tentavam fazer um `ALTER TABLE conversations` para adicionar colunas extras. Porém, a tabela `conversations` sequer havia sido criada ainda, pois ela é de responsabilidade do Alembic (que ainda não tinha rodado). Isso causava um erro fatal no startup do banco, colocando o container num loop de reinicialização.
* **A Correção:** Os scripts `.sql` 01 e 02 foram esvaziados (deixados apenas com comentários), pois todas as tabelas e colunas que eles tentavam criar já estavam codificadas corretamente nas migrations do Alembic (`20260419_191734_add_platform_tables_and_seed_sandbox.py`).

### 2. Tentativa de Inserção Prematura na Tabela `sandboxes`
* **O Erro:** `relation "sandboxes" does not exist` durante o `init_db()` da API.
* **A Causa:** A migration `20260419_124133_seed_default_sandbox.py` tentava fazer um `INSERT` na tabela `sandboxes`. No entanto, devido à evolução do projeto, a tabela `sandboxes` só seria criada na migration seguinte (`20260419_191734_add_platform_tables_and_seed_sandbox.py`). Isso ocorreu porque inicialmente a tabela era criada por SQL cru no volume, e a migration apenas inseria os dados.
* **A Correção:** A migration `124133_seed_default_sandbox` foi transformada num "no-op" (funções `upgrade()` e `downgrade()` com `pass`). A inserção da sandbox padrão já ocorre de forma idempotente na migration seguinte, logo após a criação da tabela.

### 3. Permissão Negada ao Criar a Extensão Vector
* **O Erro:** `permission denied to create extension "vector"`.
* **A Causa:** A migration `20260423_024627_add_agents_and_skills_with_vector_.py` tentava executar `CREATE EXTENSION IF NOT EXISTS vector`. O Alembic, rodando através da API com o usuário `cappy` (não superusuário), sofria bloqueio do PostgreSQL, pois extensões só podem ser criadas por administradores.
* **A Correção:** A instrução foi removida do Alembic, pois o script `services/postgres/00-extensions.sql` já garante que a extensão seja criada na primeira inicialização do banco, quando o entrypoint ainda roda com privilégios de `root` interno.

### 4. Remoção de Colunas de Tabela Inexistente (`cappy_sessions`)
* **O Erro:** `UndefinedTableError: relation "cappy_sessions" does not exist`.
* **A Causa:** A migration `20260420_005033_drop_legacy_conversation_columns.py` possuía um bloco para deletar colunas antigas (`ALTER TABLE cappy_sessions DROP COLUMN IF EXISTS`). Contudo, como limpamos a tabela legada dos scripts SQL originais e do Alembic, a tabela inteira deixou de existir nas novas instalações. O Postgres rejeita o comando caso a própria tabela não exista.
* **A Correção:** O laço de repetição que tentava fazer `ALTER TABLE cappy_sessions` foi removido inteiramente da migration.

## Conclusão e Lições Aprendidas

1. **Evite duplicar responsabilidades:** Se o Alembic é utilizado para orquestrar o banco de dados, os scripts em `/docker-entrypoint-initdb.d/` devem ser estritamente reservados para setup estrutural que requer **superusuário** (como `CREATE DATABASE`, `CREATE EXTENSION`, criação de roles e concessões de permissões). Tabelas e dados devem ficar apenas nas migrations.
2. **Reconstrução da Imagem:** Qualquer mudança na pasta `alembic` exige que a imagem `cappycloud-api` seja reconstruída com o comando `docker compose up -d --build api`. Como a pasta é copiada (`COPY`) para dentro do container durante o processo de build do Docker, mudanças locais nos arquivos `.py` das migrations não surtem efeito na inicialização se o container não for "buildado" novamente.
3. **Idempotência Limitada:** `IF NOT EXISTS` e `DROP COLUMN IF EXISTS` são eficientes, mas não protegem contra a ausência da estrutura "pai" (não pode remover uma coluna caso a tabela toda não exista).
