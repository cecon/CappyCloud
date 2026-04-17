# Build a partir da raiz do repositório:
#   docker build -f services/api/Dockerfile .

FROM python:3.14-slim-bookworm

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libffi-dev \
    && rm -rf /var/lib/apt/lists/*

COPY services/api/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY proto/openclaude.proto /proto/openclaude.proto
RUN python -m grpc_tools.protoc \
    -I/proto \
    --python_out=/app \
    --grpc_python_out=/app \
    /proto/openclaude.proto

COPY services/cappycloud_agent /app/cappycloud_agent
COPY services/api/app /app/app
COPY services/api/alembic.ini /app/alembic.ini
COPY services/api/alembic /app/alembic

ENV PYTHONPATH=/app

# Porta interna (evita 8000; o mapeamento no host é `API_PORT` no docker-compose)
ENV PORT=8080
EXPOSE 8080

CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
