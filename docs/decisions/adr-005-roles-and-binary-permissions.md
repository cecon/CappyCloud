# ADR-005 — Papéis (ADMIN/USER) e Permissões Binárias por Recurso

**Status:** Proposta
**Data:** 2026-05-16
**Contexto:** CappyCloud — preparação para produção multi-tenant com controle de acesso a sandboxes, repositórios e modelos LLM

---

## Contexto

Hoje a tabela `User` ([orm_models.py:74](services/api/app/infrastructure/orm_models.py:74))
não tem campo de papel/role, e não há nenhuma camada de autorização além da
verificação de autenticação (JWT). O endpoint `/register`
([auth.py:22](services/api/app/adapters/primary/http/auth.py:22)) é público e
qualquer usuário autenticado tem acesso indiscriminado a todos os recursos da
plataforma.

Para entrar em produção precisamos:

1. Separar quem administra a plataforma de quem usa.
2. Controlar quem pode usar quais sandboxes, repositórios e modelos LLM.
3. Bloquear cadastro público e centralizar criação de usuários em ADMIN.
4. Deixar a UI consistente: o usuário não vê o que não pode usar.

Existem duas direções clássicas: enum simples de papel (`ADMIN | USER`) ou
RBAC completo com tabelas `Role`, `Permission`, `RolePermission`. RBAC é
flexível mas custa modelagem, UI e testes extras. Hoje os requisitos cabem
em 2 papéis e permissões binárias por recurso.

---

## Decisão

### 1. Papel como enum no `User`

Adicionar campo `role: UserRole` ao `User`, com enum `ADMIN | USER`. Default
em migração existente: `USER`. Primeiro ADMIN é criado por seed/CLI durante
deploy inicial.

### 2. Permissões binárias por recurso

Permissões são relações N:N entre `User` e cada recurso controlado.
Sem níveis (read/write), sem escopo (escopo é o próprio recurso):

```text
UserSandboxAccess(user_id, sandbox_id)
UserRepositoryAccess(user_id, repository_id)
UserModelAccess(user_id, model_id)
```

Presença da linha = tem acesso. Ausência = não tem.

`ADMIN` ignora as três tabelas: sempre vê tudo, sempre pode usar tudo.

### 3. ADMIN é quem administra

- Cadastrar/desativar usuários (ADMIN ou USER).
- Promover/rebaixar papel.
- Criar/clonar/configurar sandboxes (ADR-004).
- Cadastrar/editar MCPs, skills globais e subagents globais (ADR-004).
- Cadastrar/sincronizar modelos LLM e providers (ADR-006).
- Atribuir/revogar acessos (`UserSandboxAccess`, `UserRepositoryAccess`,
  `UserModelAccess`).

### 4. USER é quem usa

- Inicia conversas selecionando sandbox + repositório + modelo entre o que
  tem acesso.
- Vê apenas seus próprios artefatos (conversas, mensagens).
- Não vê telas de administração.
- Não cadastra usuários, sandboxes, MCPs, skills globais nem modelos.

### 5. Defesa em profundidade

A UI filtra dropdowns pelo que o usuário tem acesso. A API repete a
validação — não confia em filtro de UI:

- Endpoint admin: decorator `require_role(ADMIN)`.
- Endpoint que aceita `sandbox_id`/`repository_id`/`model_id`: guard valida
  que o usuário tem acesso ao recurso (ou é ADMIN).
- Filtros de listagem (GET /sandboxes, /repositories, /models): query
  injeta `WHERE` por `user_id` automaticamente para USER.

### 6. Endpoint `/register` torna-se interno

`POST /auth/register` deixa de ser público. Passa a exigir `ADMIN` (decorator
`require_role`). O primeiro ADMIN não passa por esse endpoint — vem de seed.

### 7. Sem refresh em cascata em revogação

Revogar acesso de um USER não interrompe sessões já abertas. A próxima
operação que validar permissão (envio de mensagem, criação de worktree)
falhará com 403. Trade-off explícito: simplicidade > resposta imediata.
A revogação em cascata pode ser feita em iteração futura via invalidação
de tokens ou sinal para a sessão.

---

## Regras derivadas

1. Todo endpoint sob `/admin/*` exige `role == ADMIN`. Endpoint que escapa
   essa regra precisa de justificativa em PR.
2. Todo endpoint que recebe `sandbox_id`, `repository_id` ou `model_id` no
   path/body precisa de guard de acesso.
3. Listagens nunca retornam recursos para os quais o usuário não tem acesso
   — exceto quando ele é ADMIN.
4. Em frontend, rotas administrativas vivem sob `/admin/*` e usam wrapper
   `<RequireAdmin>` análogo ao `<ProtectedPage>` atual
   ([App.tsx:25](web/src/App.tsx:25)).
5. Auditoria mínima: criação/edição/exclusão de usuário e atribuição/revogação
   de acesso geram registro em log estruturado (não é tabela de auditoria
   formal nesta ADR — apenas log).
6. Migração do esquema atual: usuários existentes recebem `role = USER` e
   acesso explícito a todos os recursos cadastrados no momento da migração
   (preserva comportamento atual). ADMIN do seed inicial é criado por
   variável de ambiente ou CLI.
7. Senhas continuam com o hash atual; esta ADR não muda esquema de auth/JWT.
8. UI de admin segue padrão Mantine já em uso ([web/package.json](web/package.json)
   tem `@mantine/core` 9). Layout: `AppShell` com navegação lateral entre
   seções (Users, Sandboxes, MCPs, Skills globais, Agents globais, Models,
   Access).

---

## Consequências

### Positivas

- Modelo é simples de explicar e implementar — 1 enum + 3 tabelas
  associativas.
- Permite multi-tenant funcional sem reescrever auth.
- UI fica consistente: USER só vê o que importa pra ele.
- ADMIN tem visão completa sem regra especial em cada endpoint (bypass
  centralizado).

### Negativas / Trade-offs

- Sem granularidade (não há "USER que pode ler X mas não escrever").
  Quando o produto precisar disso, evoluir para RBAC.
- Sem grupos/equipes. Atribuir acesso a 50 usuários para 10 sandboxes é
  500 inserts manuais — ferramenta de bulk-assign pode ser necessária
  cedo.
- Bypass de ADMIN é regra global, não scoped: ADMIN da plataforma vê
  conversas de todos os usuários. Se houver requisito de privacidade
  por usuário (mesmo contra ADMIN), esta ADR não atende.
- Revogação sem cascata é surpresa para o operador. Documentar bem na
  UI ("a revogação só vale para sessões novas").

---

## Alternativas consideradas

### RBAC completo (Role + Permission + RolePermission)

Rejeitado para a 1ª iteração. Bom quando o produto precisa de papéis
customizados por tenant. Hoje só temos dois papéis. Custaria 4–5 tabelas
extras + UI de gestão de roles, sem ganho funcional imediato.

### Permissões com níveis (read/write/admin) por recurso

Rejeitado. Hoje "acesso" é binário pelo fluxo: USER consome (lê e usa),
ADMIN configura (cria/edita). Não há terceira camada útil.

### Grupos/Equipes intermediando o acesso

Rejeitado para a 1ª iteração. Útil em organizações grandes, mas adiciona
camada de modelagem (grupos, membros, ACL por grupo) e UI. Pode ser
adicionado depois sem quebrar este modelo (basta uma tabela
`UserGroup` + resolver permissões via união).

### Soft delete vs disable

Decisão de desativar usuário (`is_active = false`) em vez de hard delete
fica desta ADR. Mantém integridade referencial com conversas, mensagens
e logs sem precisar de soft-delete genérico.

---

## Referências

- [ADR-004](adr-004-sandbox-lifecycle-and-registry.md) — sandbox como recurso
- [services/api/app/infrastructure/orm_models.py](services/api/app/infrastructure/orm_models.py)
- [services/api/app/adapters/primary/http/auth.py](services/api/app/adapters/primary/http/auth.py)
- [services/api/app/application/use_cases/auth.py](services/api/app/application/use_cases/auth.py)
- [web/src/App.tsx](web/src/App.tsx)
- [web/src/api.ts](web/src/api.ts)
