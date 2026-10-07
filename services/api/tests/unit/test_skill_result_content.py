"""O agente recebe o conteúdo da skill, não só o resumo (até o tamanho do trecho)."""

from __future__ import annotations

import uuid
from types import SimpleNamespace

from app.adapters.primary.http import skills_search
from app.adapters.secondary import repository_mcp_tool_gateway as gateway
from app.infrastructure import document_ingester


def _skill(content: str, summary: str = "Quando usar", document_id=None):
    return SimpleNamespace(content=content, summary=summary, document_id=document_id)


def test_skill_manual_entrega_o_conteudo_e_nao_so_o_resumo() -> None:
    content = "# Regra\n" + "x" * 5000
    for fn in (skills_search._result_summary, gateway._skill_summary):
        assert fn(_skill(content)) == content
        assert fn(_skill("", summary="só resumo")) == "só resumo"


def test_conteudo_corta_em_6000_como_o_trecho_de_documento() -> None:
    big = "y" * 9000
    for fn in (skills_search._result_summary, gateway._skill_summary):
        assert len(fn(_skill(big))) == 6000
        assert len(fn(_skill(big, document_id=uuid.uuid4()))) == 6000


def test_documento_vira_trechos_de_6000_com_sobreposicao() -> None:
    chunks = document_ingester.chunk_text("palavra " * 3000)
    assert all(len(chunk) <= 6000 for chunk in chunks)
    assert len(chunks) >= 4
