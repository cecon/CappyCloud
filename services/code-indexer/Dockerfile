# ──────────────────────────────────────────────────────────────
# CappyCloud Code Indexer
#
# Indexa repositórios de código em:
#   - pgvector (busca semântica por embeddings)
#   - Neo4j    (grafo AST: calls, imports, herança)
#
# Build:
#   docker build -t cappycloud-code-indexer:latest ./services/code-indexer
# ──────────────────────────────────────────────────────────────
FROM python:3.12-slim

# ── System dependencies ───────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
        git \
        curl \
        ca-certificates \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ── Python dependencies ───────────────────────────────────────
# Instala torch CPU-only primeiro para evitar baixar os 1,3 GB da versão CUDA.
RUN pip install --no-cache-dir \
        torch==2.6.0+cpu torchvision==0.21.0 \
        --extra-index-url https://download.pytorch.org/whl/cpu
COPY services/code-indexer/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Pre-download embedding model so the first request é rápido ─
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

# ── Application code ──────────────────────────────────────────
COPY services/code-indexer/app /app/app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
