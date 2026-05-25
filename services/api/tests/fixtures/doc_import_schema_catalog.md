# Schema Test

## 7. Catalogo estrutural completo

#### dbo.users  (10 linhas)
- PK: id
- Colunas:
  - `id` int PK
  - `tenant_id` int FK->dbo.tenants.id
  - `email` nvarchar(255) NULL
  - `bad line without type`

#### dbo.tenants  (3 linhas)
- PK: id
- Colunas:
  - `id` int PK
  - `name` nvarchar(100)

#### dbo.user_roles  (20 linhas)
- PK: user_id, role_id
- Colunas:
  - `user_id` int PK FK->dbo.users.id
  - `role_id` int PK FK->dbo.roles.id

#### dbo.roles  (4 linhas)
- PK: id
- Colunas:
  - `id` int PK
  - `name` nvarchar(80) NULL

#### dbo.audit_log  (0 linhas)
- PK: id
- Colunas:
  - `id` bigint PK
  - `user_id` int NULL FK->external.users.id
