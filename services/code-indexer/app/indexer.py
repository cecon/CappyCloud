"""
Orquestra a indexação do workspace de um container sandbox:
  1. Lê arquivos direto do container via Docker API (tar stream — sem git clone)
  2. Parseia AST (chunks + nós + relações)
  3. Gera embeddings em lote (sentence-transformers local)
  4. Persiste em pgvector (busca semântica) + Neo4j (grafo AST)
"""
from __future__ import annotations

import asyncio
import io
import logging
import tarfile
from pathlib import Path
from typing import Optional

import docker  # type: ignore
import docker.errors  # type: ignore

from . import graph_store, vector_store
from .ast_parser import parse_file, supported_extensions
from .embeddings import embed

log = logging.getLogger(__name__)

# Estado de indexação em memória (por user_id)
_status: dict[str, dict] = {}

MAX_FILE_SIZE = 500_000   # bytes — ignora arquivos grandes demais
MAX_FILES_PER_INDEX = 5_000

_SKIP_DIRS = frozenset({
    ".git", "node_modules", "__pycache__", ".venv", "venv",
    "dist", "build", ".mypy_cache", ".pytest_cache", "migrations",
    ".eggs", "*.egg-info",
})


def get_status(user_id: str) -> dict:
    return _status.get(user_id, {"status": "idle"})


async def trigger_index(
    user_id: str,
    container_id: str,
    workspace_path: str = "/workspace/main",
    force: bool = False,
) -> None:
    """Dispara indexação assíncrona em background."""
    if _status.get(user_id, {}).get("status") == "indexing" and not force:
        log.info("Indexação já em andamento para %s — ignorando.", user_id)
        return

    _status[user_id] = {
        "status": "indexing",
        "progress": 0.0,
        "files_indexed": 0,
        "error": None,
    }
    asyncio.create_task(_run_index(user_id, container_id, workspace_path))


async def _run_index(
    user_id: str,
    container_id: str,
    workspace_path: str,
) -> None:
    try:
        log.info(
            "Indexação headless: user=%s  container=%s  path=%s",
            user_id, container_id[:12], workspace_path,
        )

        # 1. Lê todos os arquivos do container via tar stream (sem git clone)
        files = await asyncio.to_thread(
            _read_workspace_from_container, container_id, workspace_path
        )
        total = len(files)
        log.info("Encontrados %d arquivos suportados no container.", total)

        # 2. Limpa índices anteriores
        await vector_store.delete_user_chunks(user_id)
        await graph_store.delete_user_graph(user_id)

        all_chunks: list[dict] = []
        indexed = 0

        for rel_path, content in files.items():
            result = parse_file(rel_path, content)

            if result.nodes or result.relations:
                await graph_store.upsert_nodes(user_id, result.nodes)
                await graph_store.upsert_relations(user_id, result.relations)

            for chunk in result.chunks:
                all_chunks.append({
                    "user_id": user_id,
                    "repo_url": f"container://{container_id[:12]}{workspace_path}",
                    "file_path": rel_path,
                    "language": chunk.language,
                    "chunk_type": chunk.chunk_type,
                    "chunk_name": chunk.chunk_name,
                    "start_line": chunk.start_line,
                    "end_line": chunk.end_line,
                    "content": chunk.content,
                })

            indexed += 1
            _status[user_id]["files_indexed"] = indexed
            _status[user_id]["progress"] = indexed / total if total else 1.0

            if len(all_chunks) >= 256:
                await _flush_chunks(all_chunks)
                all_chunks.clear()

        if all_chunks:
            await _flush_chunks(all_chunks)

        _status[user_id] = {
            "status": "ready",
            "progress": 1.0,
            "files_indexed": indexed,
            "error": None,
        }
        log.info("Indexação concluída: user=%s  %d arquivos.", user_id, indexed)

    except Exception as exc:
        log.error("Erro na indexação de %s: %s", user_id, exc, exc_info=True)
        _status[user_id] = {
            "status": "error",
            "progress": _status.get(user_id, {}).get("progress", 0.0),
            "files_indexed": _status.get(user_id, {}).get("files_indexed", 0),
            "error": str(exc),
        }


def _read_workspace_from_container(
    container_id: str,
    workspace_path: str,
) -> dict[str, str]:
    """
    Lê o workspace inteiro do container via Docker tar stream.
    Retorna dict {caminho_relativo: conteúdo_utf8}.
    Roda em thread (API Docker é síncrona).
    """
    client = docker.from_env()
    try:
        container = client.containers.get(container_id)
    except docker.errors.NotFound:
        raise RuntimeError(f"Container {container_id[:12]} não encontrado.")

    # get_archive devolve (generator de chunks bytes, stat dict)
    stream, _ = container.get_archive(workspace_path)

    buf = io.BytesIO()
    for chunk in stream:
        buf.write(chunk)
    buf.seek(0)

    exts = supported_extensions()
    files: dict[str, str] = {}

    with tarfile.open(fileobj=buf, mode="r:*") as tar:
        for member in tar.getmembers():
            if not member.isfile():
                continue
            if member.size > MAX_FILE_SIZE:
                continue

            # caminho relativo limpo (tar inclui o dir raiz no nome)
            parts = Path(member.name).parts
            # remove o primeiro componente se for "." ou o nome do dir raiz
            if parts and parts[0] in (".", "main", workspace_path.lstrip("/")):
                rel = str(Path(*parts[1:])) if len(parts) > 1 else parts[0]
            else:
                rel = member.name

            # ignora diretórios proibidos
            rel_parts = set(Path(rel).parts)
            if rel_parts & _SKIP_DIRS:
                continue

            # filtra por extensão suportada
            if Path(rel).suffix.lower() not in exts:
                continue

            f = tar.extractfile(member)
            if f is None:
                continue
            try:
                files[rel] = f.read().decode("utf-8", errors="replace")
            except Exception:
                continue

            if len(files) >= MAX_FILES_PER_INDEX:
                break

    return files


async def _flush_chunks(chunks: list[dict]) -> None:
    """Gera embeddings e persiste um lote de chunks."""
    texts = [c["content"] for c in chunks]
    vectors = await asyncio.to_thread(embed, texts)
    for chunk, vec in zip(chunks, vectors):
        chunk["embedding"] = vec
    await vector_store.insert_chunks(chunks)
