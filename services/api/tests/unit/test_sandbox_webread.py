"""webread (sandbox): lê páginas que barram o WebFetch; artigos Zendesk pela API."""

from __future__ import annotations

import importlib.util
import json
import urllib.error
from pathlib import Path

import pytest

_PATH = Path(__file__).resolve().parents[3] / "sandbox" / "webread.py"
_spec = importlib.util.spec_from_file_location("sandbox_webread", _PATH)
assert _spec and _spec.loader
webread = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(webread)

ARTICLE = (
    "https://centraldeatendimento.totvs.com/hc/pt-br/articles/37280831407511-"
    "Cross-Segmentos-TSS-NFSE-Falha-de-Schema"
)


def test_url_de_artigo_zendesk_vira_url_da_api() -> None:
    assert webread.zendesk_api_url(ARTICLE) == (
        "https://centraldeatendimento.totvs.com/api/v2/help_center/pt-br/articles/37280831407511.json"
    )
    assert webread.zendesk_api_url("https://centraldeatendimento.totvs.com/hc/pt-br") is None


def test_html_vira_texto_sem_script_nem_menu() -> None:
    markup = (
        "<nav>Menu</nav><h2>Causa</h2><p>Falha&nbsp;de <b>schema</b></p>"
        "<script>track()</script><ul><li>Atualize o TSS</li></ul>"
    )
    assert webread.html_to_text(markup) == "Causa\n\nFalha de schema\n\n- Atualize o TSS"


def test_artigo_vem_da_api_com_titulo_e_fonte(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def fake_get(url: str) -> tuple[str, str]:
        calls.append(url)
        article = {
            "title": "NFSE - Falha de Schema",
            "html_url": ARTICLE,
            "body": "<p>Causa: indDest</p>",
        }
        return url, json.dumps({"article": article})

    monkeypatch.setattr(webread, "_get", fake_get)

    text = webread.read(ARTICLE)

    assert calls == [webread.zendesk_api_url(ARTICLE)]
    assert text == f"# NFSE - Falha de Schema\nFonte: {ARTICLE}\n\nCausa: indDest"


def test_sem_api_le_a_pagina_como_navegador(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_get(url: str) -> tuple[str, str]:
        if "/api/v2/" in url:
            raise urllib.error.URLError("sem api")
        return "https://exemplo.com/final", "<h1>Título</h1><p>Texto</p>"

    monkeypatch.setattr(webread, "_get", fake_get)

    assert webread.read(ARTICLE.replace("totvs.com", "exemplo.com")) == (
        "Fonte: https://exemplo.com/final\n\nTítulo\n\nTexto"
    )


def test_corta_texto_longo_e_avisa_erro_http(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(webread, "read", lambda url: "x" * 50)
    assert webread.main(["https://a", "--max-chars", "10"]) == 0
    assert "cortado em 10 caracteres" in capsys.readouterr().out

    def forbidden(url: str) -> str:
        raise urllib.error.HTTPError(url, 403, "Forbidden", None, None)  # type: ignore[arg-type]

    monkeypatch.setattr(webread, "read", forbidden)
    assert webread.main(["https://a"]) == 1
    assert "HTTP 403" in capsys.readouterr().err
