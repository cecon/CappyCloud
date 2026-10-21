# Feature Specification: Admins por workspace

**Feature Branch**: `feat/workspace-admins`
**Created**: 2026-10-21
**Status**: Draft
**Input**: "crie uma feature para os admins terem acesso por workspace, então ele é admin apenas no proteus, ele e o Alef" (Eduardo, 21/10/2026). Hoje só o super admin libera acesso, reseta senha e mexe no workspace; os responsáveis do PROTHEUS (Rodolfo e Aleff) dependem dele para tudo.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Super admin marca um usuário como admin de um workspace (Priority: P1)

O super admin abre Admin → Usuários → Acessos → Workspaces e, além de liberar o workspace, marca "admin" nele. A pessoa continua USER no resto da plataforma.

**Why this priority**: sem isso nada mais existe; é o que transforma Rodolfo e Aleff em admins do PROTHEUS.

**Independent Test**: marcar um USER como admin do PROTHEUS; `GET /api/auth/me` dele passa a trazer o id do PROTHEUS em `admin_workspace_ids`; ao desmarcar, some.

**Acceptance Scenarios**:

1. **Given** um USER com acesso ao PROTHEUS, **When** o super admin liga "admin" no PROTHEUS, **Then** o usuário vira admin só do PROTHEUS.
2. **Given** um USER sem acesso ao workspace, **When** o super admin liga "admin", **Then** o acesso é concedido junto.
3. **Given** um admin de workspace, **When** ele tenta ligar "admin" para outra pessoa, **Then** recebe 403 (só ADMIN global promove).

### User Story 2 - Admin de workspace acompanha o uso do workspace dele (Priority: P1)

Rodolfo abre o menu e vê Dashboard, Conversas e Relatórios, sempre restritos ao PROTHEUS.

**Independent Test**: logado como admin do PROTHEUS, listar `/api/admin/conversations` sem filtro devolve só conversas do PROTHEUS; pedir conversa ou dashboard de outro workspace dá 403.

**Acceptance Scenarios**:

1. **Given** admin do PROTHEUS, **When** abre Conversas sem filtro, **Then** só aparecem conversas do PROTHEUS.
2. **Given** admin do PROTHEUS, **When** abre uma conversa de outro workspace (ou sem workspace) pelo id, **Then** recebe 403.
3. **Given** admin do PROTHEUS, **When** abre Dashboard ou Relatórios, **Then** os números e a lista de workspaces cobrem só o PROTHEUS.

### User Story 3 - Admin de workspace gerencia as pessoas do workspace dele (Priority: P1)

Rodolfo vê os usuários do PROTHEUS, dá e tira acesso ao PROTHEUS, redefine senha e cria usuário novo já com acesso ao PROTHEUS.

**Independent Test**: como admin do PROTHEUS, criar `novo@x.com`; ele aparece na lista com acesso ao PROTHEUS e com os mesmos modelos LLM do criador; redefinir a senha dele funciona; redefinir a de um ADMIN global ou de alguém fora do PROTHEUS dá 403.

**Acceptance Scenarios**:

1. **Given** admin do PROTHEUS, **When** abre Usuários, **Then** vê só quem tem acesso a um workspace que ele administra.
2. **Given** admin do PROTHEUS, **When** cria um e-mail novo, **Then** nasce USER, com troca de senha obrigatória, acesso ao PROTHEUS e os mesmos modelos LLM liberados para o criador.
3. **Given** admin do PROTHEUS, **When** "cria" um e-mail que já existe como USER, **Then** a pessoa só ganha acesso ao PROTHEUS (nada mais muda).
4. **Given** admin do PROTHEUS, **When** tenta dar acesso a outro workspace, mexer em ADMIN global ou mudar papel, **Then** recebe 403.
5. **Given** admin do PROTHEUS, **When** redefine a senha de um USER do PROTHEUS, **Then** a senha volta para a temporária (24 h, troca obrigatória), como no super admin.

### User Story 4 - Admin de workspace edita o workspace dele (Priority: P2)

Rodolfo abre Admin → Workspaces, vê só o PROTHEUS e edita CLAUDE.md, "chamado obrigatório" e "modo de planejamento", e usa a aba de conhecimento.

**Acceptance Scenarios**:

1. **Given** admin do PROTHEUS, **When** salva o CLAUDE.md, **Then** o workspace é sincronizado como hoje.
2. **Given** admin do PROTHEUS, **When** tenta trocar repositórios, nome, ativar/desativar, criar ou excluir workspace, **Then** recebe 403.

### Edge Cases

- Admin de workspace que também é ADMIN global: vale o ADMIN global (vê tudo).
- Tirar o acesso de alguém ao workspace também tira o "admin" daquele workspace (é a mesma linha).
- Admin de workspace não pode tirar o próprio acesso nem o próprio "admin" (evita ficar trancado para fora); o super admin pode.
- Usuário com acesso a dois workspaces, um administrado por Rodolfo: Rodolfo vê o usuário, redefine a senha dele e só mexe no acesso ao workspace que administra.
- Conversa sem workspace (repositório avulso): invisível para admin de workspace.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O acesso de um usuário a um workspace MUST ter um indicador "admin do workspace", ligado e desligado por ADMIN global (inclui super admin). ADMIN global também libera e tira acesso a workspaces de outros usuários.
- **FR-002**: `GET /api/auth/me` MUST devolver `admin_workspace_ids` (vazio para quem não administra nenhum).
- **FR-003**: Rotas de conversas, dashboard, relatórios e CSV de chamados MUST aceitar admin de workspace e limitar dados aos workspaces que ele administra, devolvendo 403 para outro workspace.
- **FR-004**: A lista de usuários MUST, para admin de workspace, trazer só usuários com acesso a algum workspace administrado por ele.
- **FR-005**: Admin de workspace MUST conseguir conceder e revogar acesso, aos workspaces que administra, para usuários USER.
- **FR-006**: Admin de workspace MUST conseguir redefinir a senha de usuários USER com acesso a um workspace que ele administra; nunca de ADMIN, super admin, outro admin de workspace ou de si mesmo.
- **FR-007**: Admin de workspace MUST conseguir criar usuário USER já com acesso a um workspace que administra; a conta herda os modelos LLM liberados para o criador e exige troca de senha. E-mail existente de USER só ganha o acesso.
- **FR-008**: Admin de workspace MUST conseguir ler o workspace que administra e alterar apenas `claude_md`, `require_ticket` e `plan_mode_enabled`, além das rotas de conhecimento; o resto continua do super admin.
- **FR-009**: Papel global (USER/ADMIN), repositórios, sandboxes, modelos, providers e skills globais MUST continuar fora do alcance do admin de workspace.
- **FR-010**: O menu e as rotas do frontend MUST mostrar a admin de workspace só Dashboard, Conversas, Relatórios, Usuários e Workspaces, com os controles que ele pode usar.

### Key Entities

- **Acesso a workspace** (`user_workspace_access`): ganha `is_admin` (bool, padrão falso).
- **Escopo de admin**: quem chama a rota administrativa — global (ADMIN) ou lista de workspaces administrados.

### Runtime Context, Security & Evidence

- Toda checagem de escopo é feita na API (use case + dependência), não só na UI (constituição IV; ADR-005).
- Evidência do estado atual: `require_role`/`require_super_admin` em `services/api/app/adapters/primary/http/deps_auth.py:93-115`; acesso binário em `infrastructure/orm_models_workspaces.py:90`; relatórios já filtram por workspace em `application/use_cases/workspace_report.py:97`.
- Senha temporária continua vindo de `ADMIN_RESET_PASSWORD`; a UI não mostra a senha.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Rodolfo e Aleff resolvem acesso, reset de senha e criação de usuário do PROTHEUS sem pedir ao super admin.
- **SC-002**: Nenhuma rota administrativa devolve dado de outro workspace a um admin de workspace (coberto por testes de 403).
- **SC-003**: Super admin e ADMIN global continuam com o comportamento atual (testes existentes passam).

## Assumptions

- Admin de workspace é USER no papel global; não vira ADMIN.
- ADMIN global (não super) mantém o que tem hoje; não ganha reset de senha.
- Admin de workspace não gerencia sandboxes, repositórios ou modelos de outros usuários; o usuário criado herda os modelos do criador.
