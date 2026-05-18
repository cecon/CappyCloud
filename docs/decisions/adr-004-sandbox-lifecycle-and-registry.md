# ADR-004 — Cadastro de Sandbox, Ciclo de Vida do Container e Periféricos

**Status:** Proposta
**Data:** 2026-05-16
**Contexto:** CappyCloud — sandboxes como entidade de primeira classe, multi-tenant, bootable on-demand em Docker Compose (dev) e Docker Swarm (prod)

---

## Contexto

Hoje a tabela `Sandbox` ([orm_models.py:32](services/api/app/infrastructure/orm_models.py:32))
existe mas tem ciclo de vida implícito: o container é assumido como já
provisionado, e o registro guarda apenas status lógico (`active|draining|offline`).
Periféricos do openclaude (MCPs, skills globais, subagents globais) ou não existem
no banco, ou estão modelados no escopo errado:

- `McpServer` ([orm_models_mcp.py:17](services/api/app/infrastructure/orm_models_mcp.py:17))
  está vinculado a `user_id`. Como uma sandbox é compartilhada por múltiplos
  usuários, MCPs precisam ser configuração da sandbox, não do usuário.
- Skills globais e subagents globais não existem em DB. Hoje só há
  skills por repositório ([orm_models_platform.py:136](services/api/app/infrastructure/orm_models_platform.py:136))
  que são injetadas no worktree.
- Não há fluxo que cadastre uma sandbox nova e suba o container correspondente
  dinamicamente — em produção (Swarm) isso vira bloqueador para multi-tenant.

A ADR-002 estabeleceu que o sandbox roda openclaude + session_server. Esta ADR
estende ADR-002 para tornar a sandbox uma entidade cadastrável, com ciclo de
vida do container gerenciado pela API e configuração de periféricos versionada
em banco.

---

## Decisão

### 1. Sandbox como entidade cadastrável

A tabela `Sandbox` passa a ser o registro autoritativo do que existe (ou
deveria existir) no orquestrador de containers. Campos relevantes:

- `name` (único): identifica o serviço/container no orquestrador.
- `runtime` (`compose | swarm`): seleciona o adapter de orquestração.
- `image`, `env` (JSON), `network`, `volumes`: parâmetros de boot.
- `container_status`: estado do container (ver item 3).
- `lifecycle_status`: estado lógico de uso (`active | draining | offline`),
  já existente, separado de `container_status`.

### 2. Topologia: 1 container por sandbox, N worktrees

Uma sandbox = um container compartilhado por todos os usuários autorizados.
A separação entre usuários e conversas é feita por worktrees dentro do
container, como já estabelecido em ADR-002. Não há container por usuário.

### 3. Estados do container

`container_status` é um enum independente do orquestrador:

```text
not_created → starting → running → configuring → configured
                                          ↘ stopped
                                          ↘ error
```

- `not_created`: existe no DB, não existe no orquestrador.
- `starting`: chamada de boot emitida, aguardando readiness.
- `running`: container vivo, antes do bootstrap de periféricos.
- `configuring`: bootstrap de MCPs/skills/agents em andamento.
- `configured`: pronto para receber conversas.
- `stopped`: container existe no orquestrador mas está parado.
- `error`: falha em qualquer transição; campo `last_error` registra causa.

### 4. Boot lazy e idempotente

Quando uma conversa é iniciada, o orquestrador da API segue o fluxo:

1. Busca sandbox por `name` no DB.
2. Consulta o adapter de runtime: o service/container existe?
3. Se não, cria. Se existe parado, inicia. Se já rodando, reusa.
4. Aguarda readiness (timeout configurável).
5. Aplica bootstrap (item 5).
6. Marca `container_status = configured`.

O fluxo é idempotente: chamar boot em sandbox já configurada é no-op (apenas
revalida readiness).

### 5. Bootstrap como materialização do DB

Toda vez que o container atinge `running`, a API materializa dentro dele:

- `~/.claude/settings.json` com a chave `mcpServers` montada a partir de
  `SandboxMcp` enabled.
- `~/.claude/skills/<name>/SKILL.md` (+ arquivos) a partir de `SandboxSkill`.
- `~/.claude/agents/<name>.md` a partir de `SandboxAgent`.
- Configuração do provider LLM (ver ADR-006).

A pasta `~/.claude/` é reescrita por completo a cada bootstrap. O DB é a
única fonte de verdade. Edições manuais dentro do container são perdidas
no próximo boot, por desenho.

### 6. Periféricos espelham o formato do openclaude

As tabelas de cadastro replicam o shape do JSON consumido pelo openclaude,
sem normalização semântica adicional:

- `SandboxMcp(sandbox_id, name, command, args[], env{}, enabled)` → vira
  `mcpServers.<name> = { command, args, env }` em `settings.json`.
- `SandboxSkill(sandbox_id, name, description, content, files[])` → vira
  pasta `skills/<name>/` com `SKILL.md` e arquivos auxiliares.
- `SandboxAgent(sandbox_id, name, description, tools[], model, system_prompt)`
  → vira arquivo `agents/<name>.md` no formato esperado pelo openclaude.

`McpServer.user_id` é descontinuado. Tabela renomeada/migrada para
`SandboxMcp.sandbox_id`.

### 7. Clone de sandbox

Clonar uma sandbox copia apenas configuração:

- Copia: linhas de `SandboxMcp`, `SandboxSkill`, `SandboxAgent`, `env`,
  `image`, `runtime`.
- Não copia: `container_status` (sempre `not_created` no clone), associações
  de `UserSandboxAccess` (ver ADR-005), repositórios cadastrados.

### 8. Runtime adapter (Compose × Swarm)

Adapter de runtime é um port com duas implementações iniciais:

```python
class SandboxRuntimeGateway(Protocol):
    def ensure_service(self, sandbox: Sandbox) -> ContainerStatus: ...
    def start(self, sandbox: Sandbox) -> ContainerStatus: ...
    def stop(self, sandbox: Sandbox) -> ContainerStatus: ...
    def status(self, sandbox: Sandbox) -> ContainerStatus: ...
    def remove(self, sandbox: Sandbox) -> None: ...
```

- `ComposeAdapter`: usa Docker SDK contra Docker Desktop em dev.
- `SwarmAdapter`: usa Docker SDK contra Swarm em prod (services, não
  containers). Em prod o Portainer é UI de observabilidade externa, não é
  chamado pela API.

A API nunca toca no socket Docker diretamente — sempre via adapter.

---

## Regras derivadas

1. Toda sandbox é cadastrável e referenciada por `name` único globalmente.
2. MCPs, skills globais e subagents globais são entidades por sandbox; só
   ADMIN pode criá-las/editá-las (ver ADR-005).
3. Skills por repositório continuam existindo no modelo atual e não são
   afetadas por esta ADR. Elas são complementares às skills globais.
4. Container só sobe via API; a UI de admin dispara `ensure_service` mas a
   lógica de transição de estados é da camada de aplicação.
5. Bootstrap é idempotente. Reiniciar bootstrap não pode corromper sessões
   ativas — worktrees em `/repos/sessions/` são preservados.
6. O campo `runtime` da sandbox decide qual adapter é injetado. Não há
   detecção automática de orquestrador.
7. `container_status` é refletido na UI admin com indicador visual e ações
   disponíveis (start/stop/rebuild/sync-config).
8. Nenhum periférico (MCP/skill/agent global) pode ser escrito direto no
   filesystem do container — sempre via DB + bootstrap.

---

## Consequências

### Positivas

- Sandboxes viram artefato versionado: criar/clonar/migrar entre ambientes
  é operação de DB + boot, não de provisionamento manual.
- Configuração de periféricos fica auditável e reproduzível.
- Dev local (Compose) e prod (Swarm) compartilham o mesmo modelo de dados e
  fluxo de boot, divergindo só no adapter.
- Clone de sandbox vira ferramenta de templating natural (sandbox "base" →
  N variantes por cliente/squad).

### Negativas / Trade-offs

- Bootstrap escreve por cima de qualquer edição manual feita dentro do
  container. Trade-off aceito: simplicidade > flexibilidade local.
- Em Swarm, `docker service create` é assíncrono e exige polling de
  readiness. Adiciona complexidade no `SwarmAdapter`.
- Migrar `McpServer.user_id → sandbox_id` é breaking change para qualquer
  consumidor existente. Mitigação: migration com transformação explícita
  (toda linha vai para a sandbox "default" e ADMIN remapeia depois).
- Single source of truth no DB significa que perder o DB perde a config das
  sandboxes (containers continuam, mas bootstrap futuro reescreve com
  estado vazio). Mitigação fora desta ADR: backup do Postgres.

---

## Alternativas consideradas

### Manter MCP por usuário

Rejeitado. Sandbox compartilhada por N usuários precisa de configuração
compartilhada. MCP por usuário criaria conflito de `mcpServers.<name>`
quando dois usuários da mesma sandbox cadastrassem o mesmo nome.

### Container por usuário ou por conversa

Rejeitado pelos mesmos motivos da ADR-002 (custo, complexidade, perde
reuso de clones de repo). Worktrees resolvem isolamento por usuário.

### Configuração de periféricos via arquivo versionado no Git

Rejeitado. Funcionaria mas exige fluxo de PR/merge para cada ajuste. Admin
da plataforma precisa de UI direta para criar/editar MCPs e skills sem
passar por commit de código.

### Bootstrap incremental (só aplica diff)

Rejeitado para a 1ª iteração. Reescrever a pasta inteira é simples e
idempotente. Diff otimiza tempo mas adiciona caminhos de falha. Pode ser
adotado depois se boot ficar lento.

### Detecção automática de runtime (compose vs swarm)

Rejeitado. Tornar explícito (`runtime` no DB) evita comportamento mágico
e permite mesma instância da API gerenciar sandboxes em ambos os runtimes
se necessário.

---

## Referências

- [ADR-002](adr-002-sandbox-runtime-and-worktree-sessions.md) — runtime base
- [services/api/app/infrastructure/orm_models.py](services/api/app/infrastructure/orm_models.py)
- [services/api/app/infrastructure/orm_models_mcp.py](services/api/app/infrastructure/orm_models_mcp.py)
- [services/api/app/infrastructure/orm_models_platform.py](services/api/app/infrastructure/orm_models_platform.py)
- [services/cappycloud_agent/_environment_manager.py](services/cappycloud_agent/_environment_manager.py)
- [docs/ARCHITECTURE.md](../ARCHITECTURE.md)
