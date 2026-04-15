"""
CappyCloud Code Indexer API
Endpoints:
  POST /index               — dispara indexação de um repo
  GET  /index/{user_id}     — status da indexação
  POST /search/semantic     — busca semântica por embedding
  POST /search/symbol       — busca símbolo por nome no grafo
  POST /search/references   — quem usa/chama um símbolo
  POST /search/callgraph    — call graph a partir de uma função
  GET  /health
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

from . import graph_store, indexer, vector_store
from .embeddings import embed_one
from .models import (
    CallGraphRequest,
    IndexRequest,
    ReferencesRequest,
    SemanticSearchRequest,
    SymbolSearchRequest,
)

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("Code Indexer iniciando — preparando schema pgvector e índices Neo4j…")
    await vector_store.get_pool()
    await graph_store.ensure_indexes()
    log.info("Code Indexer pronto.")
    yield
    await graph_store.close_driver()


app = FastAPI(title="CappyCloud Code Indexer", lifespan=lifespan)


# ── Indexação ─────────────────────────────────────────────────

@app.post("/index", status_code=202)
async def start_index(req: IndexRequest):
    """Dispara indexação headless do workspace já presente no container sandbox."""
    await indexer.trigger_index(
        user_id=req.user_id,
        container_id=req.container_id,
        workspace_path=req.workspace_path,
        force=req.force,
    )
    return {"status": "started", "user_id": req.user_id}


@app.get("/index/{user_id}")
async def index_status(user_id: str):
    """Retorna o status atual da indexação para o usuário."""
    return indexer.get_status(user_id)


# ── Busca semântica ───────────────────────────────────────────

@app.post("/search/semantic")
async def semantic_search(req: SemanticSearchRequest):
    """Busca chunks de código por similaridade semântica."""
    embedding = embed_one(req.query)
    results = await vector_store.semantic_search(
        user_id=req.user_id,
        query_embedding=embedding,
        limit=req.limit,
        language=req.language,
    )
    return {"results": results, "count": len(results)}


# ── Busca no grafo AST ────────────────────────────────────────

@app.post("/search/symbol")
async def symbol_search(req: SymbolSearchRequest):
    """Localiza funções, classes ou métodos pelo nome."""
    results = await graph_store.find_symbol(
        user_id=req.user_id,
        symbol=req.symbol,
        symbol_type=req.symbol_type,
    )
    return {"results": results, "count": len(results)}


@app.post("/search/references")
async def find_references(req: ReferencesRequest):
    """Encontra todos os lugares que chamam ou importam um símbolo."""
    results = await graph_store.find_references(
        user_id=req.user_id,
        symbol=req.symbol,
        file_path=req.file_path,
    )
    return {"results": results, "count": len(results)}


@app.post("/search/callgraph")
async def call_graph(req: CallGraphRequest):
    """Retorna o call graph a partir de uma função (máx. depth níveis)."""
    if req.depth > 6:
        raise HTTPException(status_code=400, detail="depth máximo é 6")
    results = await graph_store.get_call_graph(
        user_id=req.user_id,
        function=req.function,
        depth=req.depth,
    )
    return {"results": results, "count": len(results)}


# ── Health ────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok"}
