---
name: api-ux
description: Use esta habilidade para melhorar a experiência do usuário a partir do lado Python/FastAPI — mensagens de erro úteis, estrutura de resposta consistente, streaming SSE fluido, paginação, estados de loading e contratos de API que reduzem fricção no frontend.
---

# API UX — CappyCloud

Guia para projetar e implementar APIs Python/FastAPI que produzam excelente experiência no frontend. O backend é parte do design system — uma API ruim força o frontend a compensar com código defensivo feio.

## 1. Mensagens de Erro

### Estrutura Padrão de Erro
```python
# schemas.py — use sempre este formato
class ErrorDetail(BaseModel):
    code: str          # machine-readable: "conversation_not_found"
    message: str       # human-readable: "Conversa não encontrada"
    field: str | None  # para erros de validação: "name"

class ErrorResponse(BaseModel):
    error: ErrorDetail
```

### Hierarquia de Códigos de Erro
```python
# Prefixos por domínio:
# auth_*        → autenticação/autorização
# conversation_ → entidade Conversation
# environment_  → entidade Environment
# skill_*       → entidade Skill
# validation_*  → erros de input do usuário
# agent_*       → erros do agente/LLM

# Exemplos:
"auth_token_expired"        # 401
"auth_permission_denied"    # 403
"conversation_not_found"    # 404
"conversation_limit_reached"# 422
"validation_field_required" # 422
"agent_unavailable"         # 503
```

### Mapeamento HTTP Status → UX
| Status | Código de Erro | UX no Frontend |
|--------|---------------|----------------|
| 400 | `validation_*` | Erro inline no campo do form |
| 401 | `auth_*` | Redirect para login |
| 403 | `auth_permission_denied` | Modal "sem permissão" |
| 404 | `*_not_found` | Página/componente de 404 inline |
| 409 | `*_conflict` | Toast de aviso com opção de resolver |
| 422 | `*_limit_*` | Modal explicativo com call-to-action |
| 429 | `rate_limit_*` | Toast com tempo de espera |
| 503 | `agent_unavailable` | Banner de status + retry automático |

### Anti-patterns de Erro
```python
# RUIM — mensagem técnica vaza para o usuário
raise HTTPException(status_code=500, detail="sqlalchemy.exc.IntegrityError")

# BOM — mensagem útil + código para o frontend agir
raise HTTPException(
    status_code=409,
    detail={"code": "conversation_name_conflict", "message": "Já existe uma conversa com este nome"}
)
```

## 2. Estrutura de Respostas

### Padrão de Lista com Paginação
```python
class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
    has_next: bool

# Parâmetros de query padrão
@router.get("/conversations")
async def list_conversations(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None),
):
```

### Padrão de Criação/Atualização
```python
# Sempre retorna o recurso completo após mutação
# Evita round-trip desnecessário no frontend

@router.post("/conversations", status_code=201)
async def create_conversation(...) -> ConversationSchema:
    result = await use_case.execute(...)
    return ConversationSchema.from_entity(result)  # recurso completo
```

### Campos de Metadata Úteis para UX
```python
class ConversationSchema(BaseModel):
    id: str
    name: str
    created_at: datetime
    updated_at: datetime
    message_count: int          # evita N+1 no frontend
    last_message_preview: str | None  # preview sem buscar mensagens
    status: Literal["idle", "running", "error"]  # estado atual
    environment_name: str | None  # desnormalizado para evitar join no frontend
```

## 3. Streaming SSE

### Padrão de Eventos
```python
# Tipos de evento padronizados — o frontend switch neles
EVENT_TYPES = {
    "thinking":      # LLM processando — ThinkingIndicator
    "tool_call":     # Tool sendo executado — ToolCallCard
    "tool_result":   # Resultado do tool
    "message_chunk": # Token do LLM — streaming de texto
    "message_done":  # Mensagem completa
    "action_required": # Usuário precisa aprovar algo — ActionRequiredCard
    "error":         # Erro durante execução
    "done":          # Stream encerrado
}

# Formato do evento
async def format_sse_event(event_type: str, data: dict) -> str:
    payload = json.dumps({"type": event_type, "data": data})
    return f"data: {payload}\n\n"
```

### Heartbeat para Evitar Timeout
```python
async def stream_with_heartbeat(generator):
    async for event in generator:
        yield event
    # Heartbeat a cada 15s se não há eventos
    # Evita que proxies e browsers fechem a conexão
    yield "data: {\"type\": \"heartbeat\"}\n\n"
```

### Tratamento de Desconexão
```python
@router.get("/conversations/{id}/stream")
async def stream_conversation(id: str, request: Request):
    async def event_generator():
        try:
            async for event in agent_stream(id):
                if await request.is_disconnected():
                    break  # limpa recursos ao desconectar
                yield await format_sse_event(event.type, event.data)
        except Exception as e:
            yield await format_sse_event("error", {"message": str(e)})
        finally:
            yield await format_sse_event("done", {})

    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

## 4. Endpoints de Status e Health

### Estado de Ambiente para UX
```python
class EnvironmentStatusSchema(BaseModel):
    id: str
    status: Literal["creating", "ready", "error", "stopped"]
    progress_percent: int | None  # 0-100 durante criação
    progress_message: str | None  # "Instalando dependências..."
    error_message: str | None
    ready_since: datetime | None
```

### Polling-friendly com ETag
```python
@router.get("/environments/{id}/status")
async def get_environment_status(
    id: str,
    response: Response,
    if_none_match: str | None = Header(None),
):
    status = await get_status(id)
    etag = compute_etag(status)

    if if_none_match == etag:
        return Response(status_code=304)  # não mudou, economiza bytes

    response.headers["ETag"] = etag
    response.headers["Cache-Control"] = "no-cache"
    return status
```

## 5. Validação com Feedback de UX

### Validação em Tempo Real (Endpoints de Validação Dedicados)
```python
# Para forms longos, ofereça validação parcial
@router.post("/conversations/validate-name")
async def validate_conversation_name(
    data: ConversationNameValidation,
    current_user: User = Depends(get_current_user),
) -> NameValidationResult:
    """Valida só o nome antes de submeter o form completo."""
    exists = await repo.name_exists(current_user.id, data.name)
    return NameValidationResult(
        valid=not exists,
        error_code="conversation_name_conflict" if exists else None,
        suggestion=await generate_name_suggestion(data.name) if exists else None,
    )
```

### Mensagens de Validação Pydantic
```python
class CreateConversationRequest(BaseModel):
    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Nome da conversa",
    )

    @field_validator("name")
    @classmethod
    def name_no_special_chars(cls, v: str) -> str:
        if not re.match(r'^[\w\s\-\.]+$', v):
            raise ValueError("Nome não pode conter caracteres especiais")
        return v.strip()
```

## 6. Performance para UX Percebida

### Time-to-First-Byte (TTFB)
```python
# Para listas: retorne os primeiros N itens imediatamente
# enquanto computa totais em background (se necessário)

@router.get("/conversations")
async def list_conversations(...):
    # Query com LIMIT — retorna rápido
    items = await repo.list(page=page, page_size=page_size)
    # Count separado só se necessário para paginação
    total = await repo.count() if page == 1 else None
    return PaginatedResponse(items=items, total=total or -1, ...)
```

### Cache de Recursos Estáticos de UX
```python
# Skills, modelos disponíveis, configurações — cache agressivo
@router.get("/ai-models")
async def list_ai_models(response: Response):
    response.headers["Cache-Control"] = "public, max-age=300"  # 5min
    return await get_available_models()
```

## 7. Checklist de API UX

Antes de entregar um novo endpoint:
- [ ] Erros usam `ErrorDetail` com `code` machine-readable
- [ ] Listas têm paginação (nunca retorne tudo sem limite)
- [ ] Criação/atualização retorna o recurso completo
- [ ] Campos desnormalizados para evitar N+1 no frontend
- [ ] SSE events têm `type` padronizado
- [ ] Validação com mensagens em português para o usuário
- [ ] Status de progresso para operações longas (ambientes, tasks)
- [ ] ETag em endpoints com polling frequente
- [ ] Testado com `code-review` + `vulnerability-auditor`
