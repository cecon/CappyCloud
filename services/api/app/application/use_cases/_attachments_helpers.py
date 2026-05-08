"""Helpers para o use-case ``StreamMessage`` lidar com anexos.

Extraídos de ``conversations.py`` para manter o ficheiro abaixo de 300 linhas.
São funções puras (recebem ports como argumentos) — facilita teste isolado.
"""

from __future__ import annotations

import uuid

from app.ports.repositories import AiModelCapabilityLookup, AttachmentRepository
from app.ports.services import AttachmentStorage


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

    model = atts[0].vision_model_used or "vision"
    sections: list[str] = [
        "## Imagens anexadas pelo utilizador",
        (
            "O utilizador anexou as imagens abaixo. Cada uma foi descrita por "
            f"um modelo de visão (`{model}`). Use estas descrições como se "
            "tivesse visto as imagens — não peça para reenviar."
        ),
    ]
    for i, att in enumerate(atts, 1):
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
