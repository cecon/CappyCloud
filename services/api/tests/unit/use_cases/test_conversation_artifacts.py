"""Tests for conversation-scoped artifact uploads."""

from __future__ import annotations

import uuid
from collections.abc import Generator
from typing import Any

from app.application.use_cases.attachments import UploadAttachment
from app.application.use_cases.conversations import CreateConversation, StreamMessage

from tests.conftest import (
    FakeAgent,
    InMemoryAttachmentRepository,
    InMemoryAttachmentStorage,
    InMemoryConversationRepository,
    InMemoryMessageRepository,
)
from tests.fakes_attachments import FakeVisionDescriber


class _CapturingAgent(FakeAgent):
    def __init__(self) -> None:
        super().__init__()
        self.last_user_message: str | None = None

    def pipe(
        self,
        user_message: str,
        model_id: str,
        messages: list[dict[str, Any]],
        body: dict[str, Any],
    ) -> Generator[str]:
        self.last_user_message = user_message
        yield from super().pipe(user_message, model_id, messages, body)


async def test_uploaded_log_artifact_is_injected_into_agent_prompt() -> None:
    user_id = uuid.uuid4()
    conv_repo = InMemoryConversationRepository()
    msg_repo = InMemoryMessageRepository()
    attachment_repo = InMemoryAttachmentRepository()
    storage = InMemoryAttachmentStorage()
    conv = await CreateConversation(conv_repo).execute(user_id, "Analise de logs")

    attachment = await UploadAttachment(
        conversations=conv_repo,
        attachments=attachment_repo,
        storage=storage,
        vision=FakeVisionDescriber(),
    ).execute(
        conversation_id=conv.id,
        user_id=user_id,
        original_filename="startup.log",
        mime_type="application/octet-stream",
        content=(
            b"2026-05-18 10:00:01 INFO boot ok\n"
            b"2026-05-18 10:00:02 ERROR Kubernetes timeout during init\n"
        ),
        max_bytes=50 * 1024 * 1024,
        image_max_bytes=8 * 1024 * 1024,
    )

    assert attachment.kind == "log"
    assert attachment.processing_status == "indexed"
    assert attachment.chunks_count == 1

    agent = _CapturingAgent()
    stream = await StreamMessage(
        conv_repo,
        msg_repo,
        agent,
        attachments=attachment_repo,
        attachment_storage=storage,
    ).execute(
        conv.id,
        user_id,
        "procure timeout do Kubernetes",
        attachment_ids=[attachment.id],
    )
    async for _ in stream:
        pass

    assert agent.last_user_message is not None
    assert "Arquivos anexados pelo utilizador" in agent.last_user_message
    assert "startup.log" in agent.last_user_message
    assert "Kubernetes timeout during init" in agent.last_user_message
    assert "linhas 1-2" in agent.last_user_message

    messages = await msg_repo.list_by_conversation(conv.id)
    user_message = next(msg for msg in messages if msg.role == "user")
    assert user_message.content == "procure timeout do Kubernetes"


async def _upload_text(
    conv_repo: InMemoryConversationRepository,
    attachment_repo: InMemoryAttachmentRepository,
    storage: InMemoryAttachmentStorage,
    conversation_id: uuid.UUID,
    user_id: uuid.UUID,
    filename: str,
    content: bytes,
) -> uuid.UUID:
    attachment = await UploadAttachment(
        conversations=conv_repo,
        attachments=attachment_repo,
        storage=storage,
        vision=FakeVisionDescriber(),
    ).execute(
        conversation_id=conversation_id,
        user_id=user_id,
        original_filename=filename,
        mime_type="application/xml",
        content=content,
        max_bytes=50 * 1024 * 1024,
        image_max_bytes=8 * 1024 * 1024,
    )
    return attachment.id


async def test_attachment_within_budget_is_injected_whole() -> None:
    from app.application.use_cases._attachments_helpers import inject_artifact_chunks

    user_id = uuid.uuid4()
    conv_repo = InMemoryConversationRepository()
    attachment_repo = InMemoryAttachmentRepository()
    storage = InMemoryAttachmentStorage()
    conv = await CreateConversation(conv_repo).execute(user_id, "XML")
    # 40 chunks de busca: antes só os 6 primeiros chegavam ao agente.
    lines = [f"<item id='{i}'>valor {i}</item>" for i in range(3000)]
    att_id = await _upload_text(
        conv_repo,
        attachment_repo,
        storage,
        conv.id,
        user_id,
        "nfse.xml",
        "\n".join(lines).encode(),
    )

    prompt = await inject_artifact_chunks(
        attachment_repo, conv.id, [att_id], "analise", "analise", storage=storage
    )

    assert "`nfse.xml` (completo, linhas 1-3000)" in prompt
    assert "<item id='0'>valor 0</item>" in prompt
    assert "<item id='2999'>valor 2999</item>" in prompt
    assert "não representam o arquivo inteiro" not in prompt


async def test_attachment_over_budget_falls_back_to_chunks() -> None:
    from app.application.use_cases._attachments_helpers import inject_artifact_chunks

    user_id = uuid.uuid4()
    conv_repo = InMemoryConversationRepository()
    attachment_repo = InMemoryAttachmentRepository()
    storage = InMemoryAttachmentStorage()
    conv = await CreateConversation(conv_repo).execute(user_id, "XML grande")
    small_id = await _upload_text(
        conv_repo, attachment_repo, storage, conv.id, user_id, "small.xml", b"<a>pequeno</a>"
    )
    big_id = await _upload_text(
        conv_repo,
        attachment_repo,
        storage,
        conv.id,
        user_id,
        "big.xml",
        ("<b>grande</b>\n" * 200).encode(),
    )

    prompt = await inject_artifact_chunks(
        attachment_repo,
        conv.id,
        [small_id, big_id],
        "grande",
        "analise",
        storage=storage,
        full_text_budget=100,
    )

    assert "`small.xml` (completo, linhas 1-1)" in prompt
    assert "### Trecho 1: `big.xml`" in prompt
    assert "não representam o arquivo inteiro" in prompt
    assert prompt.endswith("---\n\nanalise")


async def test_artifact_chunks_do_not_leak_between_conversations() -> None:
    user_id = uuid.uuid4()
    conv_repo = InMemoryConversationRepository()
    msg_repo = InMemoryMessageRepository()
    attachment_repo = InMemoryAttachmentRepository()
    storage = InMemoryAttachmentStorage()
    create = CreateConversation(conv_repo)
    first = await create.execute(user_id, "Primeira")
    second = await create.execute(user_id, "Segunda")

    upload = UploadAttachment(
        conversations=conv_repo,
        attachments=attachment_repo,
        storage=storage,
        vision=FakeVisionDescriber(),
    )
    first_attachment = await upload.execute(
        conversation_id=first.id,
        user_id=user_id,
        original_filename="private.txt",
        mime_type="text/plain",
        content=b"conteudo exclusivo da primeira conversa",
        max_bytes=50 * 1024 * 1024,
        image_max_bytes=8 * 1024 * 1024,
    )

    agent = _CapturingAgent()
    stream = await StreamMessage(
        conv_repo,
        msg_repo,
        agent,
        attachments=attachment_repo,
        attachment_storage=storage,
    ).execute(
        second.id,
        user_id,
        "use o anexo de outra conversa",
        attachment_ids=[first_attachment.id],
    )
    async for _ in stream:
        pass

    assert agent.last_user_message == "use o anexo de outra conversa"


async def test_image_kind_can_be_detected_by_extension_when_mime_is_missing() -> None:
    user_id = uuid.uuid4()
    conv_repo = InMemoryConversationRepository()
    attachment_repo = InMemoryAttachmentRepository()
    storage = InMemoryAttachmentStorage()
    conv = await CreateConversation(conv_repo).execute(user_id, "Imagem")

    attachment = await UploadAttachment(
        conversations=conv_repo,
        attachments=attachment_repo,
        storage=storage,
        vision=FakeVisionDescriber(description="imagem processada"),
    ).execute(
        conversation_id=conv.id,
        user_id=user_id,
        original_filename="print.png",
        mime_type="application/octet-stream",
        content=b"fake image bytes",
        max_bytes=50 * 1024 * 1024,
        image_max_bytes=8 * 1024 * 1024,
    )

    assert attachment.kind == "image"
    assert attachment.processing_status == "described"
    assert attachment.vision_description is not None
    assert "imagem processada" in attachment.vision_description


def test_config_text_files_are_accepted_as_text_artifacts() -> None:
    from app.application.use_cases.artifact_processing import detect_artifact_kind

    for name in ("nfse_3505708.ini", "nfse_3505708.cfg", "app.conf", "query.sql"):
        assert detect_artifact_kind(name, "") == "text"
