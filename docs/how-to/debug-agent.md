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
    ↓  Docker SDK
Container  cappy_env_<slug>
    ↓  gRPC :50051
GrpcSession (_grpc_session.py)  →  openclaude
    ↓
OpenRouter LLM
```

---

## 1. Verificar containers em execução

```bash
# Listar todos os containers do CappyCloud
docker ps --filter "name=cappy_env_"

# Ver estado de um ambiente específico
docker inspect cappy_env_<slug> --format '{{.State.Status}}'
```

Estados possíveis: `running`, `exited`, `created`, `paused`, `none` (não existe).

---

## 2. Ler logs do container

```bash
# Últimas 100 linhas
docker logs cappy_env_<slug> --tail 100

# Seguir em tempo real
docker logs cappy_env_<slug> --follow

# Logs do processo openclaude dentro do container
docker exec cappy_env_<slug> cat /tmp/openclaude.log
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
HGETALL session:<user_id>:<chat_id>

# Ver estado de um ambiente
HGETALL env:<slug>
```

Campos relevantes:
- `container_id` — ID do container Docker
- `container_ip` — IP interno na rede `cappycloud_net`
- `grpc_port` — porta gRPC (padrão 50051)
- `worktree_path` — caminho do worktree git dentro do container

---

## 4. Testar conectividade gRPC

```bash
# Verificar se o servidor gRPC está respondendo
docker exec cappy_env_<slug> grpc_health_probe -addr=localhost:50051

# Ou com nc
docker exec cappy_env_<slug> nc -zv localhost 50051
```

---

## 5. Inspecionar worktrees git

```bash
# Listar worktrees do ambiente
docker exec cappy_env_<slug> git -C /repos/<slug> worktree list

# Ver estado do worktree de uma sessão
docker exec cappy_env_<slug> git -C /repos/<slug>/sessions/<chat_id> status
```

---

## 6. Forçar limpeza de sessão travada

Se uma sessão ficou em estado inconsistente:

```bash
# 1. Parar o container
docker stop cappy_env_<slug>

# 2. Remover o container
docker rm cappy_env_<slug>

# 3. Limpar chaves Redis do ambiente
redis-cli -u redis://localhost:16379 DEL env:<slug>

# 4. Limpar sessões desse ambiente (cuidado: apaga histórico em memória)
redis-cli -u redis://localhost:16379 KEYS "session:*" | xargs redis-cli DEL
```

O próximo request ao ambiente recriará o container automaticamente.

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
