"""Helpers para o use-case ``StreamMessage`` lidar com anexos.

Extraídos de ``conversations.py`` para manter o ficheiro abaixo de 300 linhas.
São funções puras (recebem ports como argumentos) — facilita teste isolado.
"""

from __future__ import annotations

import uuid

from app.application.use_cases._attachment_excerpts import (
    EXCERPT_BUDGET_CHARS,
    LocalIndex,
    build_local_index,
    coverage_note,
    select_excerpts,
)
from app.application.use_cases.artifact_processing import extract_artifact_text
from app.domain.entities import ConversationArtifactChunk, MessageAttachment
from app.ports.repositories import AiModelCapabilityLookup, AttachmentRepository
from app.ports.services import AttachmentStorage

# Texto total de anexos que vai inteiro no prompt (~40k tokens).
FULL_TEXT_BUDGET_CHARS = 150_000


async def can_send_native_vision(
    model_caps: AiModelCapabilityLookup | None,
    override_model: str | None,
) -> bool:
    """``True`` quando o utilizador escolheu um modelo vision-capaz."""
    if not override_model or model_caps is None:
        return False
    try:
        return await model_caps.is_vision_capable(override_model)
    except Exception:
        return False


async def load_attachment_bytes(
    attachments: AttachmentRepository | None,
    storage: AttachmentStorage | None,
    conversation_id: uuid.UUID,
    attachment_ids: list[uuid.UUID],
) -> list[dict] | None:
    """Lê bytes do storage para enviar nativamente via gRPC.

    Devolve ``None`` se algo der errado (caller cai para o caminho C de
    descrição textual). Falha silenciosa para não bloquear o turno.
    """
    if attachments is None or storage is None:
        return None
    try:
        atts = await attachments.list_by_ids(attachment_ids, conversation_id)
    except Exception:
        return None
    if not atts:
        return None
    out: list[dict] = []
    for att in atts:
        if att.kind != "image" and not att.mime_type.lower().startswith("image/"):
            continue
        try:
            content = await storage.read(att.storage_path)
        except Exception:
            continue
        out.append(
            {
                "mime_type": att.mime_type,
                "data": content,
                "original_filename": att.original_filename,
            }
        )
    return out or None


async def inject_attachments(
    attachments: AttachmentRepository | None,
    conversation_id: uuid.UUID,
    attachment_ids: list[uuid.UUID] | None,
    prompt: str,
) -> str:
    """Prepende ao prompt as descrições dos anexos selecionados.

    Os anexos foram pré-processados pelo vision describer no upload, de modo
    que aqui é só ler ``vision_description`` de cada um e injectar em formato
    legível para o agente. Falha silenciosa: se o repo não estiver wired ou
    os ids forem inválidos, devolve o prompt original.
    """
    if not attachment_ids or attachments is None:
        return prompt
    try:
        atts = await attachments.list_by_ids(attachment_ids, conversation_id)
    except Exception:
        return prompt
    if not atts:
        return prompt

    image_atts = [att for att in atts if att.kind == "image" or att.mime_type.startswith("image/")]
    if not image_atts:
        return prompt

    model = image_atts[0].vision_model_used or "vision"
    sections: list[str] = [
        "## Imagens anexadas pelo utilizador",
        (
            "O utilizador anexou as imagens abaixo. Cada uma foi descrita por "
            f"um modelo de visão (`{model}`). Use estas descrições como se "
            "tivesse visto as imagens — não peça para reenviar."
        ),
    ]
    for i, att in enumerate(image_atts, 1):
        desc = att.vision_description or (
            "[descrição indisponível — pergunte ao utilizador o que estava "
            "na imagem se for crítico]"
        )
        sections.append(
            f"### Imagem {i}: `{att.original_filename}` "
            f"({att.mime_type}, {att.size_bytes} bytes)\n\n{desc}"
        )
    sections.append("---\n\n## Mensagem do utilizador\n\n" + prompt)
    return "\n\n".join(sections)


async def inject_artifact_chunks(
    attachments: AttachmentRepository | None,
    conversation_id: uuid.UUID,
    attachment_ids: list[uuid.UUID] | None,
    query: str,
    prompt: str,
    *,
    storage: AttachmentStorage | None = None,
    limit: int = 6,
    full_text_budget: int = FULL_TEXT_BUDGET_CHARS,
    excerpt_budget: int = EXCERPT_BUDGET_CHARS,
) -> str:
    """Prepende os arquivos anexados à conversa.

    Arquivos que cabem em ``full_text_budget`` vão inteiros; os que não cabem
    entram como trechos: sempre o começo do arquivo, os trechos com marcadores
    de erro (logs) e os recuperados pela busca (ver ``_attachment_excerpts``).
    """
    if not attachment_ids or attachments is None:
        return prompt
    try:
        atts = await attachments.list_by_ids(attachment_ids, conversation_id)
    except Exception:
        return prompt
    artifact_atts = [
        att for att in atts if att.kind != "image" and not att.mime_type.startswith("image/")
    ]
    if not artifact_atts:
        return prompt

    full_files, remaining, local = await _read_full_texts(
        storage, artifact_atts, full_text_budget, conversation_id
    )
    searched: list[ConversationArtifactChunk] = []
    if remaining:
        try:
            searched = await attachments.search_chunks(
                conversation_id=conversation_id,
                attachment_ids=[att.id for att in remaining],
                query=query,
                limit=limit,
            )
        except Exception:
            searched = []
    excerpts = select_excerpts(remaining, local, searched, budget=excerpt_budget)
    if not full_files and not excerpts:
        return prompt

    sections = ["## Arquivos anexados pelo utilizador"]
    for idx, (att, text) in enumerate(full_files, 1):
        sections.append(
            f"### Arquivo {idx}: `{att.original_filename}` "
            f"(completo, linhas 1-{text.count(chr(10)) + 1})\n\n```text\n{text}\n```"
        )
    if excerpts:
        covered = {e.attachment_id for e in excerpts}
        notes = [
            coverage_note(att, local.get(att.id), excerpts)
            for att in remaining
            if att.id in covered
        ]
        sections.append(
            "Os arquivos abaixo são grandes demais para ir inteiros. Vão só trechos: "
            "o começo de cada arquivo, os trechos com marcadores de erro e os "
            "recuperados pela busca. Eles não representam o arquivo inteiro.\n\n"
            + "\n".join(notes)
            + "\n\nSe a resposta depender de uma parte que não veio, diga quais linhas "
            "faltam e peça ao utilizador esse intervalo."
        )
        by_id = {att.id: att for att in remaining}
        for idx, excerpt in enumerate(excerpts, 1):
            chunk_att = by_id.get(excerpt.attachment_id)
            filename = chunk_att.original_filename if chunk_att else str(excerpt.attachment_id)
            location = _format_chunk_location(
                excerpt.line_start, excerpt.line_end, excerpt.page_start
            )
            sections.append(
                f"### Trecho {idx}: `{filename}`{location}\n\n```text\n{excerpt.content}\n```"
            )
    return "\n\n".join(sections) + "\n\n---\n\n" + prompt


async def _read_full_texts(
    storage: AttachmentStorage | None,
    artifact_atts: list[MessageAttachment],
    budget: int,
    conversation_id: uuid.UUID,
) -> tuple[
    list[tuple[MessageAttachment, str]],
    list[MessageAttachment],
    dict[uuid.UUID, LocalIndex],
]:
    """Separa os anexos que cabem inteiros dos que vão por trechos.

    Para os que vão por trechos, recalcula os chunks a partir do original.
    """
    if storage is None:
        return [], artifact_atts, {}
    full: list[tuple[MessageAttachment, str]] = []
    remaining: list[MessageAttachment] = []
    local: dict[uuid.UUID, LocalIndex] = {}
    for att in artifact_atts:
        try:
            content = await storage.read(att.storage_path)
            text = extract_artifact_text(att.original_filename, att.mime_type, content)
        except Exception:
            remaining.append(att)
            continue
        if text and len(text) <= budget:
            full.append((att, text))
            budget -= len(text)
        else:
            remaining.append(att)
            local[att.id] = build_local_index(att, conversation_id, text, content)
    return full, remaining, local


def _format_chunk_location(
    line_start: int | None,
    line_end: int | None,
    page_start: int | None,
) -> str:
    if line_start is not None and line_end is not None:
        return f" (linhas {line_start}-{line_end})"
    if page_start is not None:
        return f" (página {page_start})"
    return ""
