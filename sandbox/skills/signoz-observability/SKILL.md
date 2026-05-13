---
name: signoz-observability
description: Guia completo de observabilidade com SignOz — instrumentação, rastreamento distribuído, métricas e logs. Quando usar e quando não usar.
---

# SignOz Observability Guide

Referência para integração e uso de **SignOz** (Open-source observability stack) em projetos CappyCloud. Use quando precisar implementar observabilidade de ponta a ponta: traces distribuídos, métricas de aplicação, logs estruturados.

## O que é SignOz?

SignOz é um stack de observabilidade open-source que coleta e visualiza:
- **Distributed Traces** (rastreamento distribuído) — compreender fluxo de requisições entre serviços
- **Metrics** — CPU, memória, latência, taxa de erro
- **Logs** — eventos estruturados com contexto de trace

Usa **OpenTelemetry** como padrão — coleta agnóstica a stack (suporta Python, Node.js, Go, Java, etc).

---

## ✅ QUANDO USAR SignOz

### Cenários Recomendados

| Cenário | Razão | Prioridade |
|---------|-------|-----------|
| Serviço em produção | Debugar problemas em tempo real sem SSH | 🔴 Alta |
| Arquitetura de microserviços | Entender latência entre serviços | 🔴 Alta |
| Pipeline de agentes | Rastrear execução de tasks e sub-tasks | 🔴 Alta |
| Integração gRPC/API | Debugar chamadas lentas/falhadas | 🟡 Média |
| Investigação de performance | Identificar gargalos sem profiler | 🟡 Média |
| Desenvolvimento local com Docker | Debugar comportamento de container | 🟢 Baixa |

### Exemplo: Quando Usar

```python
# ✅ USE SignOz aqui:
# - Serviço FastAPI em produção
# - Precisa debugar por que um endpoint está lento
# - Quer ver o trace completo: HTTP → banco de dados → redis → chamada gRPC

from opentelemetry import trace, metrics
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

# Setup tracer
trace_exporter = OTLPSpanExporter(
    endpoint="signoz:4317",  # gRPC endpoint
    insecure=True
)
trace.set_tracer_provider(TracerProvider())
trace.get_tracer_provider().add_span_processor(
    BatchSpanProcessor(trace_exporter)
)
```

---

## ❌ QUANDO NÃO USAR SignOz

### Condições que BLOQUEIAM o uso

| Condição | Razão | Alternativa |
|----------|-------|-------------|
| ❌ **service.name não configurado** | SignOz precisa identificar qual serviço gera o trace — sem nome, é impossível filtrar no UI | Configure `OTEL_SERVICE_NAME` primeiro |
| ❌ **Variáveis de ambiente OTEL não definidas** | OpenTelemetry não sabe para onde enviar spans | Configure `.env` ou docker-compose antes |
| ❌ **Servidor SignOz indisponível** | Spans serão perdidos ou acumularão em buffer | Verifique se docker-compose está rodando |
| ❌ **Desenvolvimento local sem Docker** | Difícil conectar ao servidor SignOz remoto | Use `localhost:4317` ou suba SignOz localmente |
| ❌ **Script one-off / job pontual** | Overhead de instrumentação > valor (traces curtos) | Use `print()` ou `logging` simples |
| ❌ **Ambiente restrito (sem gRPC)** | Firewall/proxy bloqueia porta 4317 | Use exportador HTTP em porta 4318 |

### Exemplo: Cenário onde NÃO usar

```python
# ❌ NÃO USE SignOz aqui:

# 1. Script sem service.name
if not os.getenv("OTEL_SERVICE_NAME"):
    print("⚠️  OTEL_SERVICE_NAME não está definida!")
    print("   Instrumentação desativada — use print() ou logging")
    # Alternativa: logging.basicConfig() + print()

# 2. Job que roda 50ms — overhead não compensa
@app.get("/health")
def health_check():
    # Instrumentação aqui seria overkill
    return {"status": "ok"}

# 3. Desenvolvimento local sem Docker
if os.getenv("ENV") == "development" and not docker_is_running():
    print("❌ SignOz não está rodando")
    print("   Inicie: docker-compose -f docker-compose.dev.yml up")
```

---

## ⚙️ Configuração Básica

### 1. Variáveis de Ambiente OBRIGATÓRIAS

```bash
# .env ou docker-compose.yml
OTEL_EXPORTER_OTLP_ENDPOINT=http://signoz:4317  # gRPC
OTEL_EXPORTER_OTLP_PROTOCOL=grpc
OTEL_SERVICE_NAME=my-service                    # ⚠️ CRÍTICO
OTEL_ENVIRONMENT=production
OTEL_RESOURCE_ATTRIBUTES=service.version=1.0.0,deployment.environment=prod
```

### 2. Docker Compose (SignOz Stack)

```yaml
# docker-compose.dev.yml
services:
  signoz:
    image: signoz/signoz:latest
    ports:
      - "3301:3301"  # Web UI
    environment:
      - CLICKHOUSE_CLUSTER=cluster_0
    depends_on:
      - clickhouse

  clickhouse:
    image: clickhouse/clickhouse-server:latest
    environment:
      - CLICKHOUSE_DB=signoz_db
    ports:
      - "9000:9000"
    volumes:
      - clickhouse_data:/var/lib/clickhouse

volumes:
  clickhouse_data:
```

### 3. Instrumentação Python (FastAPI)

```python
# app/main.py
from opentelemetry import trace, metrics
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from fastapi import FastAPI
import os

app = FastAPI()

# Validar service.name
service_name = os.getenv("OTEL_SERVICE_NAME")
if not service_name:
    raise ValueError("⚠️  OTEL_SERVICE_NAME deve estar configurada!")

# Setup Tracer Provider
trace_exporter = OTLPSpanExporter(
    endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317"),
    insecure=True
)
tracer_provider = TracerProvider(resource=Resource.create({
    "service.name": service_name,
    "service.version": "1.0.0"
}))
tracer_provider.add_span_processor(BatchSpanProcessor(trace_exporter))
trace.set_tracer_provider(tracer_provider)

# Setup Meter Provider (métricas)
metric_exporter = OTLPMetricExporter(
    endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317"),
    insecure=True
)
metric_reader = PeriodicExportingMetricReader(metric_exporter)
meter_provider = MeterProvider(metric_readers=[metric_reader])
metrics.set_meter_provider(meter_provider)

# Auto-instrumentar componentes
FastAPIInstrumentor.instrument_app(app)
SQLAlchemyInstrumentor().instrument()
RequestsInstrumentor().instrument()
```

---

## 📊 Instrumentação Avançada

### Custom Spans (Rastreamento Manual)

```python
from opentelemetry import trace

tracer = trace.get_tracer(__name__)

# Criar span manualmente
def process_order(order_id: str):
    with tracer.start_as_current_span("process_order") as span:
        span.set_attribute("order.id", order_id)
        span.set_attribute("order.status", "processing")
        
        # Código aqui será rastreado
        result = calculate_total(order_id)
        
        span.set_attribute("order.total", result)
        return result
```

### Adicionar Atributos Contextuais

```python
# Atributos no request (útil para correlacionar traces)
@app.middleware("http")
async def add_trace_context(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    
    # Adicionar ao trace
    span = trace.get_current_span()
    span.set_attribute("request.id", request_id)
    span.set_attribute("request.method", request.method)
    span.set_attribute("request.path", request.url.path)
    
    response = await call_next(request)
    span.set_attribute("response.status", response.status_code)
    return response
```

### Capturar Erros em Spans

```python
from opentelemetry.trace import Status, StatusCode

try:
    # Código que pode falhar
    result = api.fetch_data()
except Exception as e:
    span = trace.get_current_span()
    span.record_exception(e)
    span.set_status(Status(StatusCode.ERROR))
    raise
```

---

## 🔍 Visualização e Debugging

### Acessar SignOz UI

```
URL: http://localhost:3301
```

### Filtros Úteis no UI

```
# Buscar por service.name
service.name = "my-service"

# Buscar by erro
status.code = "ERROR"

# Buscar por latência > 1s
duration > 1000ms

# Buscar por operação específica
operation_name = "GET /api/users"

# Combinar: traces com erro que demoraram > 500ms
status.code = "ERROR" AND duration > 500ms
```

### Query Examples

```sql
-- Latência percentil P95 por endpoint
SELECT 
    quantile(0.95)(duration_ms) as p95_latency,
    http_method,
    http_url
FROM traces
WHERE service_name = 'my-service'
GROUP BY http_method, http_url

-- Taxa de erro por serviço
SELECT 
    COUNT(*) as total_spans,
    countIf(status_code = 'ERROR') as error_count,
    (error_count / total_spans * 100) as error_rate_pct
FROM traces
WHERE timestamp > now() - INTERVAL 1 HOUR
GROUP BY service_name
```

---

## 🚨 Troubleshooting

### Problema: Spans não aparecem no SignOz

**Checklist:**

```bash
# 1. Verificar variáveis de ambiente
echo $OTEL_SERVICE_NAME          # Deve não estar vazio
echo $OTEL_EXPORTER_OTLP_ENDPOINT  # Deve apontar para SignOz

# 2. Verificar conectividade
curl -X POST http://signoz:4317/some-path
# Deve falhar com "connection refused" se SignOz está down

# 3. Verificar logs do container
docker logs <container-id> | grep -i "otel\|trace"

# 4. Forçar verbose logging
OTEL_LOG_LEVEL=debug python app/main.py
```

### Problema: Spans com dados incompletos

**Solução:**

```python
# Ensure Resource está configurado corretamente
from opentelemetry.sdk.resources import Resource

resource = Resource.create({
    "service.name": os.getenv("OTEL_SERVICE_NAME"),
    "service.version": "1.0.0",
    "environment": os.getenv("OTEL_ENVIRONMENT", "dev"),
    "deployment.environment": os.getenv("OTEL_ENVIRONMENT", "dev")
})

tracer_provider = TracerProvider(resource=resource)
```

### Problema: Alto overhead de processamento

**Dicas:**

```python
# 1. Ajustar batch size
BatchSpanProcessor(exporter, schedule_delay_millis=5000, max_queue_size=512)

# 2. Usar sampler para reduzir volume
from opentelemetry.sdk.trace.sampling import TraceIdRatioBased

trace.set_tracer_provider(TracerProvider(
    sampler=TraceIdRatioBased(0.1)  # Coletar 10% dos traces
))

# 3. Desabilitar em ambientes com baixa relevância
if os.getenv("ENV") not in ["production", "staging"]:
    # Usar NoOpSpanProcessor (descarta traces)
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
    tracer_provider.add_span_processor(SimpleSpanProcessor(InMemorySpanExporter()))
```

---

## 📋 Checklist de Implementação

- [ ] `OTEL_SERVICE_NAME` está definido em `.env` e `docker-compose.yml`
- [ ] SignOz está rodando (`docker ps | grep signoz`)
- [ ] OpenTelemetry SDK instalado: `pip install opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp`
- [ ] Instrumentadores instalados: `pip install opentelemetry-instrumentation-fastapi opentelemetry-instrumentation-sqlalchemy`
- [ ] FastAPI/servico está instrumentado (chamar `FastAPIInstrumentor.instrument_app(app)`)
- [ ] Teste: fazer request e verificar em `localhost:3301`
- [ ] Documentar serviço no README do projeto

---

## 📚 Referências

- **OpenTelemetry Docs**: https://opentelemetry.io/docs/
- **SignOz Setup**: https://signoz.io/docs/install/
- **OTEL Instrumentation**: https://opentelemetry.io/docs/reference/specification/protocol/exporter/
- **gRPC vs HTTP**: gRPC (port 4317) é mais eficiente; HTTP (port 4318) é mais compatível com firewalls

---

**Scope**: Global — aplicável a todos os serviços  
**Última atualização**: maio 2026
