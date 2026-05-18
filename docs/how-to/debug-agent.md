# Como depurar problemas com o agente

Guia de diagnóstico para problemas com sessões de agente, containers Docker
e comunicação gRPC.

---

## Mapa de componentes

```
FastAPI (StreamMessage use case)
    ↓
AgentPort.pipe()  →  Pipeline (cappycloud_pipeline.py)
    ↓
EnvironmentManager (_environment_manager.py)
    ↓  HTTP interno :8080
Sandbox  cappycloud-sandbox
    ↓  session_server cria /repos/sessions/<session_id>/<alias>
    ↓  gRPC :50051
GrpcSession (_grpc_session.py)  →  openclaude
    ↓
OpenRouter LLM
```

---

## 1. Verificar containers em execução

```bash
# Listar todos os containers do CappyCloud
docker ps --filter "name=cappycloud-sandbox"

# Ver estado do sandbox
docker inspect cappycloud-sandbox --format '{{.State.Status}}'
```

Estados possíveis: `running`, `exited`, `created`, `paused`, `none` (não existe).

---

## 2. Ler logs do container

```bash
# Últimas 100 linhas
docker logs cappycloud-sandbox --tail 100

# Seguir em tempo real
docker logs cappycloud-sandbox --follow

# Logs do processo openclaude dentro do container
docker exec cappycloud-sandbox cat /tmp/openclaude.log
```

---

## 3. Inspecionar sessão no Redis

O `SessionStore` guarda o estado de cada sessão em Redis com TTL.

```bash
# Conectar ao Redis
redis-cli -u redis://localhost:16379

# Listar todas as chaves de sessão
KEYS session:*

# Ver estado de uma sessão
HGETALL sandbox:<user_id>:<chat_id>
```

Campos relevantes:
- `sandbox_id` — sandbox alocado para a conversa
- `sandbox_name` — nome lógico do sandbox
- `grpc_port` — porta gRPC (padrão 50051)
- `session_root` — raiz da sessão em `/repos/sessions/<session_id>`
- `repos` — repositórios e worktrees da conversa

---

## 4. Testar conectividade gRPC

```bash
# Verificar se o servidor gRPC está respondendo
docker exec cappycloud-sandbox grpc_health_probe -addr=localhost:50051

# Ou com nc
docker exec cappycloud-sandbox nc -zv localhost 50051

# Verificar o sidecar HTTP de sessões
docker exec cappycloud-sandbox curl -fsS http://localhost:8080/health
```

---

## 5. Inspecionar worktrees git

```bash
# Listar worktrees do clone persistente
docker exec cappycloud-sandbox git -C /repos/<slug> worktree list

# Ver estado do worktree de uma sessão
docker exec cappycloud-sandbox \
  git -C /repos/sessions/<session_id>/<repo-alias> status
```

---

## 6. Forçar limpeza de sessão travada

Se uma sessão ficou em estado inconsistente:

```bash
# 1. Remover a sessão do cache
redis-cli -u redis://localhost:16379 DEL sandbox:<user_id>:<chat_id>

# 2. Remover o diretório da sessão no sandbox, se necessário
docker exec cappycloud-sandbox rm -rf /repos/sessions/<session_id>

# 3. Em último caso, reiniciar o sandbox inteiro
docker restart cappycloud-sandbox
```

O próximo request da conversa recriará a sessão e os worktrees de forma
idempotente.

---

## 7. Fluxo do ActionRequired

Quando o frontend não responde a um `ActionRequired`:

1. O gRPC stream fica **pausado** — o agente não avança
2. `GrpcSession.pending_action` fica populado
3. A próxima mensagem do utilizador é detectada como resposta (`pipe()` verifica
   `session.pending_action` antes de decidir como rotear)

> **Comportamento atual:** o pipeline auto-aprova com `"yes"` qualquer
> `ActionRequired`. Ver o bloco `elif event_type == "action"` em
> `services/cappycloud_agent/cappycloud_pipeline.py:304`.

Para desativar o auto-approve e expor o prompt ao utilizador, remova esse bloco
e implemente o fluxo de resposta no frontend.

---

## 8. Verificar logs da API FastAPI

```bash
# Via Docker Compose
docker compose logs api --tail 100 --follow

# Buscar erros gRPC
docker compose logs api | grep -i grpc

# Buscar erros de sessão
docker compose logs api | grep -i "session\|environment\|pipeline"
```

---

## 9. Problemas comuns

| Sintoma | Causa provável | Solução |
|---------|----------------|---------|
| Timeout ao iniciar agente | Container demorando para subir | Verificar logs do container; aumentar `SANDBOX_IDLE_TIMEOUT` |
| "Erro ao conectar ao agente" | gRPC não disponível | Verificar se `openclaude` iniciou dentro do container |
| Resposta em branco | `OPENROUTER_API_KEY` inválida ou modelo incorreto | Verificar variável de ambiente e modelo em `OPENROUTER_MODEL` |
| Container não inicia | Imagem `cappycloud-sandbox:latest` não existe | `docker build -t cappycloud-sandbox:latest services/sandbox/` |
| Worktree já existe | Sessão anterior não foi limpa | Forçar limpeza (passo 6) |
