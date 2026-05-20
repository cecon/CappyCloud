# ADR-007 — Pivô para CappyRepo: MCP Read-Only de Repositórios com Governança

**Status:** Proposto
**Data:** 2026-05-20
**Contexto:** CappyCloud → CappyRepo

---

## Contexto

O CappyCloud atual é uma plataforma de agentes IA com web UI, openclaude
(gRPC) em sandboxes Docker, integração OpenRouter e worktrees por sessão.
Após uso real, identificamos que:

1. **O gargalo prático não é editar código**, e sim **disponibilizar código**
   pra quem precisa entendê-lo. Edição, hoje, é commodity (Cursor, Claude
   Code, Copilot, etc.).
2. Manter web UI de chat + openclaude + OpenRouter consome esforço
   significativo sem diferencial competitivo. Qualquer cliente MCP
   (Claude Desktop, Cursor, Windsurf, Cline, Zed) já entrega essa parte.
3. Existe um caso de uso real e mal atendido: **times de Relações com
   Cliente / Suporte Técnico N1 que, por governança, não podem ter
   acesso ao código-fonte**, mas precisam tirar dúvidas sobre o produto
   ("esse erro 5021 vem de onde?", "essa regra de cálculo existe?",
   "essa flag está habilitada por padrão?").

A solução que ninguém oferece bem hoje é: **uma LLM atua como firewall
entre o código e o humano não-credenciado**. A LLM lê o código via MCP;
o humano recebe a resposta filtrada; o código bruto nunca sai do
servidor.

---

## Decisão

Pivotar o produto para **CappyRepo**: uma plataforma MCP read-only de
repositórios com camada de governança, redaction e auditoria.

### Princípios

1. **Read-only por contrato.** O servidor MCP não expõe nenhuma
   operação de escrita, execução ou mutação de git. Não há `write_file`,
   `exec`, `git_push`. Tentativas são recusadas no servidor, não no
   prompt.
2. **LLM como firewall.** O cliente MCP (Claude Desktop, Cursor, etc.)
   roda no host do usuário; a LLM consulta o CappyRepo; a resposta volta
   pro usuário já filtrada. O código bruto não trafega até o usuário a
   menos que a política permita.
3. **Governança server-side, sempre.** Auth, RBAC, redaction e audit
   são decididos no servidor. Cliente e LLM não são confiáveis pra
   enforcement.
4. **Stateless por chamada, sessão por token.** Cada chamada MCP carrega
   o token; cada token tem escopo, expiração e política vinculados.

### Arquitetura alvo

```
┌─────────────────────────────────────────────────────────────┐
│  Cliente MCP do usuário (Cursor / Claude Desktop / etc.)    │
│  Conecta em: https://cappyrepo.io/mcp/<token>               │
└──────────────────────┬──────────────────────────────────────┘
                       │ HTTPS + token
┌──────────────────────▼──────────────────────────────────────┐
│  CappyRepo MCP Server (novo)                                │
│  ├─ Auth         valida token, expiração, revogação         │
│  ├─ RBAC         confere escopo (repo, path) por chamada    │
│  ├─ Rate limit   por token + detecção de anomalia           │
│  ├─ Tools        search / read / find_refs / explain        │
│  ├─ Redaction    filtra antes da LLM e antes da resposta    │
│  └─ Audit        log forense de toda chamada                │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│  Backend FastAPI (mantido, simplificado)                    │
│  ├─ Admin / RBAC / billing                                  │
│  ├─ Gestão de repos, tokens, políticas                      │
│  ├─ Indexação semântica (LSP/AST, ADR-003)                  │
│  └─ Audit store                                             │
└──────────────────────┬──────────────────────────────────────┘
                       │
           PostgreSQL  │  Redis  │  Repos clonados (read-only)
```

### Tools MCP do MVP

| Tool             | Descrição                                          |
| ---------------- | -------------------------------------------------- |
| `search_code`    | Busca textual/semântica no repo (com redaction)    |
| `read_file`      | Lê um arquivo (sujeito a path RBAC + redaction)    |
| `list_directory` | Lista paths (sujeito a path RBAC)                  |
| `find_symbol`    | Busca definição de símbolo (LSP)                   |
| `find_refs`      | Busca referências de um símbolo (LSP)              |
| `explain`        | Pede explicação textual de um trecho/símbolo       |

Não existirão neste MVP: `write_file`, `apply_patch`, `run_command`,
`git_*`.

### Políticas de redaction (configuráveis por repo)

- **Modo "explicação pura":** a LLM recebe o código, mas o servidor
  **bloqueia respostas que contenham trechos literais** com mais de N
  linhas consecutivas do fonte. Resposta vira prosa.
- **Modo "snippet curto":** snippets até N linhas são permitidos, paths
  são substituídos por hashes opacos.
- **Modo "referência abstrata":** respostas só podem citar nomes de
  módulo de alto nível, nunca caminhos nem código.

Redaction tem duas camadas:

1. **Pré-LLM (acesso):** arquivos com pattern de segredo (`.env`,
   `secrets/`, chaves privadas, certificados) são bloqueados no
   servidor. A LLM nunca os vê.
2. **Pós-LLM (saída):** a resposta da LLM passa por um filtro que
   aplica a política ativa. Output guard determinístico, não
   confia no modelo.

### Auditoria

Cada chamada gera um registro com:

- `token_id`, `user_id`, `team_id`, `repo_id`
- `tool`, `args` (com paths normalizados)
- `files_touched` (lista de arquivos lidos pela LLM nessa cadeia)
- `policy_applied`, `redactions_performed`
- `response_excerpt` (hash + tamanho; conteúdo retido por X dias se
  política permitir)
- `timestamp`, `client_ip`, `client_user_agent`

---

## Consequências

### O que **sai** do CappyCloud atual

- `web/` — frontend de chat React. (Será substituído por um painel
  admin mínimo, não um IDE.)
- `services/cappycloud_agent/` — pipeline openclaude, gRPC session,
  environment manager. Não há mais agente de execução.
- `services/sandbox/` — Dockerfile do agente, session_server.js,
  worktrees. Não há mais execução remota.
- `proto/openclaude.proto` — contrato gRPC.
- Integração OpenRouter (`adapters/secondary/llm_*`).
- ADR-002 (sandbox + worktrees) e ADR-006 (LLM provider port) ficam
  obsoletos — mantidos como histórico.

### O que **fica** (e fica simplificado)

- `services/api/` (FastAPI) — auth, RBAC, billing, admin, gestão de
  repos/tokens/políticas, audit store.
- Arquitetura Hexagonal (ADR-001).
- Indexação semântica LSP/AST (ADR-003) — agora vira **core**, não
  ferramenta sob demanda.
- PostgreSQL + Redis.

### O que **entra novo**

- `services/mcp_server/` — servidor MCP read-only (provavelmente
  Python, expõe HTTP+SSE conforme spec MCP).
- `services/redaction/` — biblioteca de redaction (pré e pós).
- `web/admin/` — painel admin enxuto (gestão de repos, tokens,
  políticas, audit log). Substitui a UI de chat.

### Riscos

1. **Prompt injection / exfil pela LLM.** Mitigação: redaction
   determinística pós-LLM. Sem isso, governança não funciona.
2. **Indexação de repos grandes.** Mitigação: indexação incremental,
   cache, limites de tamanho.
3. **Compatibilidade MCP entre clientes.** Mitigação: aderir
   estritamente ao spec; testar com Claude Desktop, Cursor, Cline.
4. **Long-running tools** (indexar, refazer embeddings). Mitigação:
   tools assíncronas (job_id + polling), nada síncrono > 10s.
5. **Migração de clientes atuais do CappyCloud.** O produto muda de
   categoria; clientes que usavam pra editar código precisam migrar
   pra Cursor/Claude Code. Comunicação clara.

---

## MVP — Fase 1 (escopo mínimo)

Objetivo: um time RC consegue conectar Claude Desktop ao CappyRepo e
tirar dúvidas sobre 1 repo, com governança básica.

1. Servidor MCP read-only com `search_code`, `read_file`,
   `list_directory`.
2. Auth por token (URL).
3. RBAC por repo (1 token = 1 repo, read-only).
4. Redaction pré-LLM (bloqueio de paths sensíveis por pattern).
5. Audit log básico (chamada + arquivos tocados).
6. Painel admin com: cadastro de repo, gerar/revogar token, ver audit.

Fora do MVP (vão pra fase 2):
- Indexação semântica LSP / `find_symbol` / `find_refs`.
- Redaction pós-LLM (output guard).
- Modos de política configuráveis.
- Anomaly detection / rate limiting avançado.
- Multi-repo por token.

---

## Decisão sobre ADRs anteriores

- **ADR-001 (Hexagonal):** mantido. Continua válido pro backend.
- **ADR-002 (Sandbox + worktrees):** **revogado**. Não há mais sandbox
  de execução.
- **ADR-003 (LSP/AST sob demanda):** **promovido**. Agora é core, não
  opcional.
- **ADR-004 (Sandbox lifecycle):** **revogado**.
- **ADR-005 (Roles + permissões binárias):** mantido, ajustado pra
  RBAC de repo/path.
- **ADR-006 (LLM provider port):** **revogado**. Não há mais LLM no
  servidor; a LLM vive no cliente MCP.
