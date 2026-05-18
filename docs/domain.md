# CappyCloud — Domínio

Entidades, regras de negócio e fluxos do domínio. Nenhuma dependência de
framework ou banco de dados. Fonte de verdade: `services/api/app/domain/`.

---

## Entidades

### User
Utilizador registado na plataforma.

| Campo             | Tipo       | Descrição                          |
|-------------------|------------|------------------------------------|
| `id`              | UUID       | Chave primária gerada na criação   |
| `email`           | str        | Normalizado em minúsculas          |
| `hashed_password` | str        | Hash bcrypt — nunca expor em JSON  |
| `created_at`      | datetime   | UTC, gerado automaticamente        |

**Regras:**
- Email validado por `validate_email()` em `domain/value_objects.py`
- Email é único na plataforma (verificado no use case `RegisterUser`)
- Password mínima de 8 caracteres (verificado por `validate_password()`)

---

### Repository
Repositório git cadastrado no catálogo do ambiente. Ele é compartilhado como
fonte de contexto, mas cada conversa recebe worktrees transitórios próprios no
sandbox.

| Campo        | Tipo     | Descrição                                    |
|--------------|----------|----------------------------------------------|
| `id`         | UUID     | Chave primária                               |
| `slug`       | str      | Identificador curto único (ex.: `meu-projeto`). Minúsculas, números e hífens. |
| `name`       | str      | Nome legível exibido na UI                   |
| `repo_url`   | str      | URL do repositório git (https)               |
| `branch`     | str      | Branch principal — padrão `"main"`           |
| `confluence_url` | str | URL base opcional do Confluence associado ao repo |
| `created_at` | datetime | UTC, gerado automaticamente                  |

**Regras:**
- `slug` é único e imutável após criação
- Slug válido: `^[a-z0-9][a-z0-9\-]{1,62}[a-z0-9]$`
- O clone persistente fica em `/repos/<slug>/` dentro do sandbox
- Worktrees de conversa ficam em `/repos/sessions/<session_id>/<repo-alias>/`
- Se `confluence_url` estiver vazio, o agente não consulta Confluence para esse
  repositório

---

### Conversation
Thread de chat pertencente a um utilizador, opcionalmente ligada a um ou mais
repositórios do catálogo.

| Campo             | Tipo         | Descrição                                           |
|-------------------|--------------|-----------------------------------------------------|
| `id`              | UUID         | Chave primária                                      |
| `user_id`         | UUID         | FK → User                                           |
| `title`           | str          | Título exibido na UI (padrão: "Nova conversa")      |
| `created_at`      | datetime     | UTC                                                 |
| `updated_at`      | datetime     | UTC — atualizado a cada nova mensagem               |
| `sandbox_id`      | UUID ou None | Sandbox alocado para execução                       |
| `repository_ids`  | list[UUID]   | Repositórios selecionados para a conversa           |

**Regras:**
- Uma Conversation pertence a exatamente um User
- Se houver repositórios selecionados, o agente recebe um `session_root`
  exclusivo em `/repos/sessions/<session_id>/`
- Cada repositório selecionado ganha um worktree próprio dentro desse
  `session_root`
- Sem repositório associado, o agente opera no workspace mínimo do sandbox

---

### Message
Mensagem persistida numa Conversation.

| Campo             | Tipo     | Descrição                                      |
|-------------------|----------|------------------------------------------------|
| `id`              | UUID     | Chave primária                                 |
| `conversation_id` | UUID     | FK → Conversation                              |
| `role`            | str      | `"user"` \| `"assistant"` \| `"system"`        |
| `content`         | str      | Texto completo (até 1 MB)                      |
| `created_at`      | datetime | UTC                                            |

**Regras:**
- Mensagens são imutáveis após persistidas
- O role `"assistant"` é agregado dos chunks SSE ao finalizar a resposta
- A ordem cronológica é garantida por `created_at` (oldest-first)

---

## Regras de negócio

### Fluxo de envio de mensagem

```
Utilizador envia texto
        ↓
  StreamMessage (use case)
        ↓  verifica ownership da conversation
  Persiste Message(role="user")
        ↓
  AgentPort.pipe() → Pipeline
        ↓  garante sandbox acessível e worktrees criados
  EnvironmentManager
        ↓  stream gRPC bidirecional persistente
  GrpcSession → openclaude (gRPC :50051)
        ↓
  LLM via OpenRouter
        ↓
  SSE chunks → frontend
```

### ActionRequired

Quando o agente precisa de confirmação humana:

1. `GrpcSession` recebe evento `ActionRequired` via gRPC
2. O stream **pausa** — nenhum novo chunk é enviado
3. O frontend exibe a pergunta ao utilizador
4. A próxima mensagem do utilizador é detectada como resposta ao `ActionRequired`
5. A resposta é roteada para `session.send_input(reply)` que retoma o stream

> **Nota atual:** o pipeline auto-aprova com `"yes"`. Para desativar,
> remover o bloco `elif event_type == "action"` em `cappycloud_pipeline.py`.

### Sessões e sandboxes

- Um ou mais sandboxes podem existir; cada sandbox roda openclaude gRPC e
  `session_server`
- Uma conversa é associada a um sandbox e a um `session_root`
- Cada repositório selecionado pela conversa ganha um worktree dentro do
  `session_root`
- Sessão gRPC inativa por `SANDBOX_IDLE_TIMEOUT` segundos (padrão: 1800) é
  removida do cache

Ver [ADR-002](decisions/adr-002-sandbox-runtime-and-worktree-sessions.md).

---

## Value Objects

Definidos em `services/api/app/domain/value_objects.py`. Usados pelos schemas
Pydantic via delegação (nunca duplicar a lógica).

| Função              | Regra                                                 |
|---------------------|-------------------------------------------------------|
| `validate_email()`  | Formato `name@domain.tld`, normaliza para minúsculas  |
| `validate_password()` | Mínimo 8 caracteres                                |
