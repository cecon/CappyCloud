# CappyCloud — Referência da API REST

Base URL: `http://localhost:38000` (desenvolvimento)

Autenticação: `Authorization: Bearer <access_token>` (exceto endpoints de auth)

---

## Autenticação (`/auth`)

### `POST /auth/register`
Regista um novo utilizador.

**Request:**
```json
{
  "email": "user@example.com",
  "password": "minimo8chars"
}
```

**Response `201`:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "user@example.com"
}
```

**Erros:**
- `400` — Email inválido, password curta ou email já registado

---

### `POST /auth/login`
Autentica e devolve JWT. Usa formato `application/x-www-form-urlencoded`
(OAuth2 Password Flow).

**Request (form-data):**
```
username=user@example.com
password=minimo8chars
```

**Response `200`:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

**Erros:**
- `401` — Credenciais inválidas

---

### `GET /auth/me`
Devolve dados do utilizador autenticado.

**Response `200`:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "user@example.com"
}
```

**Erros:**
- `401` — Token inválido ou expirado

---

## Ambientes (`/environments`)

Ambientes de repositório globais legados. Eles representam um repositório
cadastrado, não um container Docker dedicado. O runtime atual usa sandboxes
registrados e worktrees transitórios por conversa; ver
`/repositories`, `/sandboxes` e
[ADR-002](../decisions/adr-002-sandbox-runtime-and-worktree-sessions.md).

### `GET /environments`
Lista todos os ambientes.

**Response `200`:**
```json
[
  {
    "id": "uuid",
    "slug": "meu-projeto",
    "name": "Meu Projeto",
    "repo_url": "https://github.com/org/repo",
    "branch": "main",
    "created_at": "2024-01-01T00:00:00Z"
  }
]
```

---

### `POST /environments`
Cria um novo ambiente.

**Request:**
```json
{
  "slug": "meu-projeto",
  "name": "Meu Projeto",
  "repo_url": "https://github.com/org/repo",
  "branch": "main"
}
```

**Validação do slug:** `^[a-z0-9][a-z0-9\-]{1,62}[a-z0-9]$`

**Response `201`:** objeto `RepoEnvOut` (mesmo formato do GET)

**Erros:**
- `409` — Slug já existe

---

### `GET /environments/{env_id}`
Detalhe de um ambiente pelo ID.

**Response `200`:** objeto `RepoEnvOut`

**Erros:**
- `404` — Ambiente não encontrado

---

### `DELETE /environments/{env_id}`
Remove o registro do ambiente no banco. Não controla container Docker dedicado.

**Response `204` (sem corpo)**

**Erros:**
- `404` — Ambiente não encontrado

---

## Conversas (`/conversations`)

### `GET /conversations`
Lista conversas do utilizador autenticado (mais recentes primeiro).

**Response `200`:**
```json
[
  {
    "id": "uuid",
    "title": "Minha conversa",
    "created_at": "2024-01-01T00:00:00Z",
    "updated_at": "2024-01-01T00:00:00Z",
    "sandbox_id": "uuid-do-sandbox",
    "ai_model_id": "uuid-do-modelo",
    "repos": [
      {
        "slug": "meu-projeto",
        "alias": "meu-projeto",
        "base_branch": "main",
        "worktree_path": "/repos/sessions/abc123/meu-projeto"
      }
    ],
    "session_root": "/repos/sessions/abc123"
  }
]
```

---

### `POST /conversations`
Cria uma nova conversa.

**Request (opcional):**
```json
{
  "title": "Nome da conversa",
  "sandbox_id": "uuid-do-sandbox",
  "repos": [
    {
      "slug": "meu-projeto",
      "alias": "meu-projeto",
      "base_branch": "main"
    }
  ]
}
```

Se `title` for omitido: `"Nova conversa"`.
Se `repos` for omitido: conversa sem repositórios selecionados.

**Response `201`:** objeto `ConversationOut`

---

## Repositórios (`/repositories`)

Catálogo de repositórios disponíveis para seleção no chat. Cada repositório pode
ter integrações opcionais próprias; campos vazios não devem acionar ferramentas
externas.

### `POST /repositories`

**Request:**
```json
{
  "slug": "meu-projeto",
  "name": "Meu Projeto",
  "clone_url": "https://github.com/org/repo.git",
  "default_branch": "main",
  "confluence_url": "https://confluence.example.com",
  "sandbox_id": "uuid-do-sandbox",
  "provider_id": null,
  "pat_token": null,
  "provider_type": "github"
}
```

`confluence_url` é opcional. Quando vazio ou omitido, o agente não consulta
`/confluence/*` para esse repositório.

**Response `201`:** objeto `RepositoryOut` com o mesmo campo
`confluence_url`.

---

### `GET /conversations/{conversation_id}/messages`
Histórico de mensagens (mais antigas primeiro).

**Response `200`:**
```json
[
  {
    "id": "uuid",
    "role": "user",
    "content": "Olá agente",
    "created_at": "2024-01-01T00:00:00Z"
  },
  {
    "id": "uuid",
    "role": "assistant",
    "content": "Olá! Como posso ajudar?",
    "created_at": "2024-01-01T00:00:01Z"
  }
]
```

**Erros:**
- `404` — Conversa não encontrada ou não pertence ao utilizador

---

### `POST /conversations/{conversation_id}/messages/stream`
Envia uma mensagem ao agente e recebe a resposta em SSE (Server-Sent Events).

**Request:**
```json
{
  "content": "Texto da mensagem do utilizador"
}
```

**Response `200` — `text/event-stream`:**

Cada evento SSE tem formato `data: <json>\n\n`. Tipos de evento:

```jsonc
// Chunk de texto do LLM
{ "type": "text", "content": "pedaço do texto" }

// Agente começou a usar uma ferramenta
{ "type": "tool_start", "tool_name": "Bash", "arguments_json": "{...}" }

// Ferramenta retornou resultado
{ "type": "tool_result", "tool_name": "Bash", "output": "...", "is_error": false }

// Erro fatal
{ "type": "error", "message": "descrição do erro" }
```

**Erros HTTP:**
- `404` — Conversa não encontrada

---

## Códigos de erro comuns

| Código | Significado |
|--------|-------------|
| `400`  | Input inválido (validação do domínio) |
| `401`  | Token ausente, inválido ou expirado |
| `404`  | Recurso não encontrado |
| `409`  | Conflito — recurso já existe (ex.: slug duplicado) |
| `422`  | Erro de validação Pydantic (campo faltando, tipo errado) |
| `500`  | Erro interno inesperado |

---

## Headers obrigatórios

```
Authorization: Bearer <jwt>
Content-Type: application/json
```

Para o endpoint SSE, adicionar:
```
Accept: text/event-stream
Cache-Control: no-cache
```
