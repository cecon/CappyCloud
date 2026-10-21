"""Abertura de PR no GitHub e no Azure DevOps (HTTP simulado)."""

from __future__ import annotations

import base64
import json

import httpx
import pytest
from app.infrastructure import git_pull_requests as prs


def _patch_http(monkeypatch: pytest.MonkeyPatch, handler) -> list[httpx.Request]:
    seen: list[httpx.Request] = []
    real_client = httpx.AsyncClient

    def record(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    def factory(*args, **kwargs):
        return real_client(transport=httpx.MockTransport(record), timeout=kwargs.get("timeout"))

    monkeypatch.setattr(prs.httpx, "AsyncClient", factory)
    return seen


async def test_github_abre_pr_com_head_e_base(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = _patch_http(
        monkeypatch,
        lambda _r: httpx.Response(
            201, json={"html_url": "https://github.com/a/b/pull/7", "number": 7}
        ),
    )
    result = await prs.open_pull_request(
        prs.parse_pr_target("https://github.com/a/b.git"),
        token="tok",
        head="cappy/b/x",
        base="main",
        title="t",
        body="d",
    )
    assert (result.url, result.number) == ("https://github.com/a/b/pull/7", 7)
    assert seen[0].url.path == "/repos/a/b/pulls"
    assert seen[0].headers["Authorization"] == "Bearer tok"
    assert json.loads(seen[0].content)["head"] == "cappy/b/x"


async def test_azure_abre_pr_com_refs_e_pat(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = _patch_http(monkeypatch, lambda _r: httpx.Response(201, json={"pullRequestId": 42}))
    target = prs.parse_pr_target("https://org@dev.azure.com/org/Meu%20Proj/_git/Seller")
    result = await prs.open_pull_request(
        target, token="pat", head="cappy/s/x", base="develop", title="t", body="d", draft=True
    )
    assert result.number == 42
    assert result.url == "https://dev.azure.com/org/Meu%20Proj/_git/Seller/pullrequest/42"
    request = seen[0]
    assert request.url.raw_path.startswith(b"/org/Meu%20Proj/_apis/git/repositories/Seller/")
    assert request.headers["Authorization"] == "Basic " + base64.b64encode(b":pat").decode()
    payload = json.loads(request.content)
    assert payload["sourceRefName"] == "refs/heads/cappy/s/x"
    assert payload["targetRefName"] == "refs/heads/develop"
    assert payload["isDraft"] is True


@pytest.mark.parametrize("url", ["https://github.com/a/b", "https://dev.azure.com/o/p/_git/r"])
async def test_erro_do_provedor_vira_pull_request_error(
    monkeypatch: pytest.MonkeyPatch, url: str
) -> None:
    _patch_http(monkeypatch, lambda _r: httpx.Response(422, text="branch já tem PR"))
    with pytest.raises(prs.PullRequestError, match="422"):
        await prs.open_pull_request(
            prs.parse_pr_target(url), token="t", head="h", base="main", title="t", body="d"
        )


async def test_sem_token_nao_chama_o_provedor() -> None:
    with pytest.raises(prs.PullRequestError, match="Sem token"):
        await prs.open_pull_request(
            prs.parse_pr_target("https://github.com/a/b"),
            token="",
            head="h",
            base="main",
            title="t",
            body="d",
        )
