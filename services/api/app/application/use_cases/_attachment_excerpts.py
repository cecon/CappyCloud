"""Escolha dos trechos de anexos grandes demais para ir inteiros no prompt.

Regras (determinísticas, nesta ordem de prioridade):

1. O começo de cada arquivo entra sempre (``HEAD_CHUNKS`` primeiros trechos).
   Em logs é ali que costuma estar o cabeçalho do erro.
2. Em logs e textos, os primeiros trechos com marcadores de erro
   (``THREAD ERROR``, ``Exception``, ``called from``...).
3. Os trechos devolvidos pela busca da pergunta.

Tudo é deduplicado por ``(attachment_id, chunk_index)`` e cabe em
``EXCERPT_BUDGET_CHARS``. Os trechos são recalculados a partir do arquivo
original (o mesmo chunking do upload), o que dá o número total de linhas e
as linhas de cada trecho mesmo para tipos que não guardam linhas no banco.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from dataclasses import dataclass, field

from app.application.use_cases.artifact_processing import LOG_CHUNK_CHARS, process_artifact
from app.domain.entities import ConversationArtifactChunk, MessageAttachment

# ~20k tokens de trechos por turno, abaixo do envio inteiro (150k chars).
EXCERPT_BUDGET_CHARS = 80_000
# Um chunk de log do upload cabe inteiro; só o último do orçamento é cortado.
EXCERPT_CHUNK_CHARS = LOG_CHUNK_CHARS
MIN_EXCERPT_CHARS = 200
HEAD_CHUNKS = 1
MARKER_CHUNKS = 3
# Comparados sem diferenciar maiúsculas (Protheus escreve "Called from").
STRONG_MARKERS = ("thread error", "called from", "exception", "traceback", "fatal")
# Nível de log em maiúsculas; minúsculo casaria com nomes como "error.log".
WEAK_MARKERS = ("ERROR",)
MARKER_KINDS = {"log", "text"}


@dataclass
class LocalIndex:
    """Chunks recalculados do arquivo original e o tamanho total dele."""

    chunks: list[ConversationArtifactChunk] = field(default_factory=list)
    total_lines: int | None = None
    total_pages: int | None = None


@dataclass(frozen=True)
class Excerpt:
    attachment_id: uuid.UUID
    chunk_index: int
    content: str
    line_start: int | None
    line_end: int | None
    page_start: int | None


def build_local_index(
    att: MessageAttachment,
    conversation_id: uuid.UUID,
    text: str,
    content: bytes,
) -> LocalIndex:
    """Recalcula os chunks do upload; ``LocalIndex()`` vazio se falhar."""
    try:
        chunks = process_artifact(
            attachment_id=att.id,
            conversation_id=conversation_id,
            filename=att.original_filename,
            mime_type=att.mime_type,
            content=content,
        ).chunks
    except Exception:
        return LocalIndex()
    if any(chunk.page_start is not None for chunk in chunks):
        pages = max(chunk.page_end or chunk.page_start or 0 for chunk in chunks)
        return LocalIndex(chunks=chunks, total_pages=pages)
    _fill_line_ranges(chunks, text)
    return LocalIndex(chunks=chunks, total_lines=text.count("\n") + 1)


def _fill_line_ranges(chunks: list[ConversationArtifactChunk], text: str) -> None:
    """Preenche as linhas de chunks de texto, que não as guardam no upload."""
    cursor = 0
    for chunk in chunks:
        if chunk.line_start is not None:
            continue
        pos = text.find(chunk.content, cursor)
        if pos < 0:
            continue
        chunk.line_start = text.count("\n", 0, pos) + 1
        chunk.line_end = chunk.line_start + chunk.content.count("\n")
        cursor = pos + 1


def select_excerpts(
    atts: list[MessageAttachment],
    local: dict[uuid.UUID, LocalIndex],
    searched: list[ConversationArtifactChunk],
    *,
    budget: int = EXCERPT_BUDGET_CHARS,
) -> list[Excerpt]:
    """Junta começo, marcadores de erro e busca, sem repetir e dentro do orçamento."""
    picked: dict[tuple[uuid.UUID, int], Excerpt] = {}
    for chunk in _candidates(atts, local, searched):
        key = (chunk.attachment_id, chunk.chunk_index)
        if key in picked:
            continue
        cap = min(EXCERPT_CHUNK_CHARS, budget)
        if cap < MIN_EXCERPT_CHARS:
            break
        excerpt = _trim(chunk, cap)
        picked[key] = excerpt
        budget -= len(excerpt.content)
    order = {att.id: idx for idx, att in enumerate(atts)}
    return sorted(
        picked.values(), key=lambda e: (order.get(e.attachment_id, len(order)), e.chunk_index)
    )


def _candidates(
    atts: list[MessageAttachment],
    local: dict[uuid.UUID, LocalIndex],
    searched: list[ConversationArtifactChunk],
) -> Iterable[ConversationArtifactChunk]:
    for att in atts:
        yield from local.get(att.id, LocalIndex()).chunks[:HEAD_CHUNKS]
    for att in atts:
        if att.kind in MARKER_KINDS:
            yield from _marker_chunks(local.get(att.id, LocalIndex()).chunks)
    for chunk in searched:
        index = local.get(chunk.attachment_id)
        # Prefere o chunk recalculado: ele tem as linhas mesmo em textos.
        if index and 0 <= chunk.chunk_index < len(index.chunks):
            yield index.chunks[chunk.chunk_index]
        else:
            yield chunk


def _marker_chunks(chunks: list[ConversationArtifactChunk]) -> list[ConversationArtifactChunk]:
    strong = [c for c in chunks if any(m in c.content.lower() for m in STRONG_MARKERS)]
    weak = [c for c in chunks if c not in strong and any(m in c.content for m in WEAK_MARKERS)]
    return (strong + weak)[:MARKER_CHUNKS]


def _trim(chunk: ConversationArtifactChunk, cap: int) -> Excerpt:
    """Corta o trecho em fronteira de linha e ajusta ``line_end`` ao que sobrou."""
    content, line_end = chunk.content, chunk.line_end
    if len(content) > cap:
        lines = content.split("\n")
        kept: list[str] = []
        size = 0
        for line in lines:
            if kept and size + len(line) + 1 > cap:
                break
            kept.append(line[:cap])
            size += len(kept[-1]) + 1
        content = "\n".join(kept)
        if chunk.line_start is not None:
            line_end = chunk.line_start + len(kept) - 1
    return Excerpt(
        attachment_id=chunk.attachment_id,
        chunk_index=chunk.chunk_index,
        content=content,
        line_start=chunk.line_start,
        line_end=line_end,
        page_start=chunk.page_start,
    )


def coverage_note(
    att: MessageAttachment,
    index: LocalIndex | None,
    excerpts: list[Excerpt],
) -> str:
    """Diz ao agente o tamanho do arquivo e quais partes ele recebeu."""
    mine = [e for e in excerpts if e.attachment_id == att.id]
    lines = [(e.line_start, e.line_end or e.line_start) for e in mine if e.line_start is not None]
    pages = sorted({e.page_start for e in mine if e.page_start is not None})
    if index and index.total_pages:
        received = ", ".join(str(p) for p in pages) or "nenhuma"
        name, total_pages = att.original_filename, index.total_pages
        return f"- `{name}`: {total_pages} páginas; recebeu as páginas {received}."
    total = f"{index.total_lines} linhas" if index and index.total_lines else "tamanho desconhecido"
    received = ", ".join(_merge_ranges(lines)) or "nenhuma"
    return f"- `{att.original_filename}`: {total} no total; recebeu as linhas {received}."


def _merge_ranges(ranges: list[tuple[int, int]]) -> list[str]:
    """Junta intervalos contíguos (``1-200`` + ``201-400`` → ``1-400``)."""
    merged: list[list[int]] = []
    for start, end in sorted(ranges):
        if merged and start <= merged[-1][1] + 1:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return [f"{start}-{end}" for start, end in merged]
