FROM ghcr.io/open-webui/pipelines:main

WORKDIR /app

# ── Extra runtime dependencies ────────────────────────────────
RUN pip install --no-cache-dir \
    grpcio>=1.62.0 \
    grpcio-tools>=1.62.0 \
    docker>=7.0.0 \
    redis>=5.0.0 \
    asyncpg>=0.29.0

# ── Generate Python gRPC stubs into /app (NOT /app/pipelines) ─
# The Pipelines framework scans /app/pipelines/ for Pipeline classes.
# Any .py file there without a Pipeline class is moved to /app/pipelines/failed/,
# breaking imports. Helpers and gRPC stubs live in /app/ instead —
# which is on sys.path but is NOT scanned by the framework.
COPY proto/ /proto/
RUN python -m grpc_tools.protoc \
    -I/proto \
    --python_out=/app \
    --grpc_python_out=/app \
    /proto/openclaude.proto

# ── Helper modules → /app  (not scanned by the framework) ─────
COPY services/pipelines/_session_store.py /app/_session_store.py
COPY services/pipelines/_docker_manager.py /app/_docker_manager.py
COPY services/pipelines/_grpc_bridge.py /app/_grpc_bridge.py
COPY services/pipelines/_grpc_session.py /app/_grpc_session.py

# ── Only the actual Pipeline class file → /app/pipelines ──────
COPY services/pipelines/cappycloud_pipeline.py /app/pipelines/cappycloud_pipeline.py

EXPOSE 9099
