"""Trechos de anexos grandes: começo sempre presente, marcadores de erro e orçamento."""

from __future__ import annotations

import re
import uuid

from app.application.use_cases._attachment_excerpts import (
    MIN_EXCERPT_CHARS,
    Excerpt,
    LocalIndex,
    coverage_note,
    select_excerpts,
)
from app.application.use_cases._attachments_helpers import inject_artifact_chunks
from app.application.use_cases.attachments import UploadAttachment
from app.application.use_cases.conversations import CreateConversation
from app.domain.entities import ConversationArtifactChunk, MessageAttachment

from tests.conftest import (
    InMemoryAttachmentRepository,
    InMemoryAttachmentStorage,
    InMemoryConversationRepository,
)
from tests.fakes_attachments import FakeVisionDescriber

QUESTION = "Analisar o motivo do error.log em anexo"


def _protheus_log(total_lines: int = 3000) -> bytes:
    """Log no formato do caso de produção: o erro está no começo do arquivo."""
    lines = [
        "THREAD ERROR ([12345], sc031610, SRVPROTHEUS)   27/11/2026   10:00:01",
        "variable does not exist CNUMPED on MATA410(MATA410.PRW) 27/11/2026 line : 1234",
        "Called from MATA410(MATA410.PRW) 27/11/2026 line : 1234",
    ]
    lines += [f"linha {i:05d} variaveis publicas e estado da thread" for i in range(4, total_lines)]
    lines.append("fim do arquivo em anexo")
    return "\n".join(lines).encode()


async def _upload(
    content: bytes, filename: str = "sc031610_20261127.log"
) -> tuple[InMemoryAttachmentRepository, InMemoryAttachmentStorage, uuid.UUID, uuid.UUID]:
    user_id = uuid.uuid4()
    conv_repo = InMemoryConversationRepository()
    attachment_repo = InMemoryAttachmentRepository()
    storage = InMemoryAttachmentStorage()
    conv = await CreateConversation(conv_repo).execute(user_id, "Log Protheus")
    attachment = await UploadAttachment(
        conversations=conv_repo,
        attachments=attachment_repo,
        storage=storage,
        vision=FakeVisionDescriber(),
    ).execute(
        conversation_id=conv.id,
        user_id=user_id,
        original_filename=filename,
        mime_type="application/octet-stream",
        content=content,
        max_bytes=50 * 1024 * 1024,
        image_max_bytes=8 * 1024 * 1024,
    )
    return attachment_repo, storage, conv.id, attachment.id


def _attachment() -> MessageAttachment:
    return MessageAttachment(
        id=uuid.uuid4(),
        conversation_id=uuid.uuid4(),
        kind="log",
        mime_type="text/plain",
        storage_path="x",
        original_filename="a.log",
    )


async def test_big_log_always_includes_the_head_for_a_generic_question() -> None:
    repo, storage, conv_id, att_id = await _upload(_protheus_log())

    prompt = await inject_artifact_chunks(
        repo, conv_id, [att_id], QUESTION, QUESTION, storage=storage, full_text_budget=1000
    )

    # A busca só casa com a última linha ("anexo"); o cabeçalho tem de vir mesmo assim.
    assert "THREAD ERROR ([12345], sc031610" in prompt
    assert "Called from MATA410" in prompt
    assert "fim do arquivo em anexo" in prompt
    assert "`sc031610_20261127.log`: 3000 linhas no total; recebeu as linhas 1-" in prompt
    assert "### Trecho 1: `sc031610_20261127.log` (linhas 1-" in prompt
    assert "não representam o arquivo inteiro" in prompt
    assert prompt.endswith("---\n\n" + QUESTION)


async def test_head_chunk_found_by_search_is_not_repeated() -> None:
    repo, storage, conv_id, att_id = await _upload(_protheus_log())

    prompt = await inject_artifact_chunks(
        repo, conv_id, [att_id], "MATA410", "o que houve?", storage=storage, full_text_budget=1000
    )

    assert prompt.count("THREAD ERROR ([12345]") == 1
    assert prompt.count("(linhas 1-") == 1


async def test_log_excerpts_respect_the_total_budget_and_report_real_ranges() -> None:
    repo, storage, conv_id, att_id = await _upload(_protheus_log())

    prompt = await inject_artifact_chunks(
        repo,
        conv_id,
        [att_id],
        "variaveis",
        "analise",
        storage=storage,
        full_text_budget=1000,
        excerpt_budget=12000,
    )

    blocks = re.findall(r"\(linhas (\d+)-(\d+)\)\n\n```text\n(.*?)\n```", prompt, re.S)
    assert len(blocks) == 2
    assert sum(len(body) for _, _, body in blocks) <= 12000
    for start, end, body in blocks:
        # A faixa anunciada bate com as linhas realmente enviadas após o corte.
        assert int(end) - int(start) + 1 == body.count("\n") + 1
    assert blocks[0][:2] == ("1", "200")
    second_start, second_end, _ = blocks[1]
    assert int(second_end) - int(second_start) + 1 < 200
    # Trechos contíguos (1-200 e 201-N) aparecem juntos na nota.
    assert second_start == "201"
    assert f"recebeu as linhas 1-{second_end}." in prompt


async def test_error_marker_chunk_in_the_middle_is_included() -> None:
    lines = [f"linha {i:05d} inicializacao normal" for i in range(1, 3001)]
    lines[1499] = "java.lang.NullPointerException at Foo.bar(Foo.java:42)"
    repo, storage, conv_id, att_id = await _upload("\n".join(lines).encode(), "app.log")

    prompt = await inject_artifact_chunks(
        repo, conv_id, [att_id], "zzz", "analise", storage=storage, full_text_budget=1000
    )

    assert "NullPointerException" in prompt
    assert "(linhas 1401-1600)" in prompt


async def test_without_storage_falls_back_to_search_with_unknown_size() -> None:
    repo, _storage, conv_id, att_id = await _upload(_protheus_log())

    prompt = await inject_artifact_chunks(repo, conv_id, [att_id], "anexo", "analise")

    assert "fim do arquivo em anexo" in prompt
    assert "`sc031610_20261127.log`: tamanho desconhecido no total" in prompt


async def test_text_excerpts_get_line_ranges_from_the_original() -> None:
    xml = "\n".join(f"<item id='{i}'/>" for i in range(1, 2001)).encode()
    repo, storage, conv_id, att_id = await _upload(xml, "nfse.xml")

    prompt = await inject_artifact_chunks(
        repo, conv_id, [att_id], "zzz", "analise", storage=storage, full_text_budget=1000
    )

    assert "`nfse.xml`: 2000 linhas no total; recebeu as linhas 1-" in prompt
    assert "### Trecho 1: `nfse.xml` (linhas 1-" in prompt


def test_select_excerpts_stops_when_budget_is_exhausted() -> None:
    att = _attachment()
    chunks = [
        ConversationArtifactChunk(
            id=uuid.uuid4(),
            attachment_id=att.id,
            conversation_id=att.conversation_id,
            chunk_index=i,
            content="ERROR " + "x" * 300,
            line_start=i + 1,
            line_end=i + 1,
        )
        for i in range(5)
    ]
    local = {att.id: LocalIndex(chunks=chunks, total_lines=5)}

    picked = select_excerpts([att], local, chunks, budget=306 * 2 + MIN_EXCERPT_CHARS - 1)

    # Dois trechos cabem inteiros; o que sobra fica abaixo do mínimo e para ali.
    assert [e.chunk_index for e in picked] == [0, 1]
    assert sum(len(e.content) for e in picked) == 612


def test_coverage_note_merges_contiguous_ranges_and_reports_pages() -> None:
    att = _attachment()

    def ex(idx: int, start: int | None, end: int | None, page: int | None = None) -> Excerpt:
        return Excerpt(att.id, idx, "c", start, end, page)

    lines_note = coverage_note(
        att, LocalIndex(total_lines=900), [ex(0, 1, 200), ex(1, 201, 400), ex(4, 801, 900)]
    )
    assert lines_note == "- `a.log`: 900 linhas no total; recebeu as linhas 1-400, 801-900."

    pages_note = coverage_note(att, LocalIndex(total_pages=7), [ex(0, None, None, 2)])
    assert pages_note == "- `a.log`: 7 páginas; recebeu as páginas 2."
