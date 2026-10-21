"""Adapter da PTAX (Banco Central): leitura da resposta, cache e falha da fonte."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import httpx
import pytest
from app.adapters.secondary import bcb_ptax
from app.adapters.secondary.bcb_ptax import PTAX_SOURCE, BcbPtaxRateProvider, parse_ptax

PAYLOAD = {
    "value": [
        {"cotacaoCompra": 5.22, "cotacaoVenda": 5.2238, "dataHoraCotacao": "2026-10-02 13:04:00.1"},
        {"cotacaoCompra": 5.01, "cotacaoVenda": 5.0119, "dataHoraCotacao": "2026-10-08 13:08:16.8"},
    ]
}


def test_parse_ptax_takes_latest_sell_rate() -> None:
    rate = parse_ptax(PAYLOAD)
    assert rate is not None
    assert (rate.rate, rate.quoted_on, rate.source) == (5.0119, date(2026, 10, 8), PTAX_SOURCE)


@pytest.mark.parametrize(
    "payload",
    [{}, {"value": []}, [], {"value": [{"dataHoraCotacao": "2026-10-08"}]}, {"value": [{}]}],
)
def test_parse_ptax_rejects_incomplete_payloads(payload: Any) -> None:
    assert parse_ptax(payload) is None


def _client(handler: Any) -> type[httpx.AsyncClient]:
    transport = httpx.MockTransport(handler)

    class _Client(httpx.AsyncClient):
        def __init__(self, **kwargs: Any) -> None:
            super().__init__(transport=transport, **kwargs)

    return _Client


async def test_provider_queries_lookback_window_and_caches_past_days(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[httpx.URL] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url)
        return httpx.Response(200, json=PAYLOAD)

    monkeypatch.setattr(bcb_ptax.httpx, "AsyncClient", _client(handler))
    provider = BcbPtaxRateProvider()
    day = date(2026, 10, 8)
    first = await provider.rate_on_or_before(day)
    second = await provider.rate_on_or_before(day)
    assert first == second
    assert first is not None and first.rate == 5.0119
    assert len(calls) == 1
    params = dict(calls[0].params)
    assert params["@dataFinalCotacao"] == "'10-08-2026'"
    assert params["@dataInicial"] == "'09-28-2026'"


async def test_provider_does_not_cache_today(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(200, json=PAYLOAD)

    monkeypatch.setattr(bcb_ptax.httpx, "AsyncClient", _client(handler))
    provider = BcbPtaxRateProvider()
    await provider.rate_on_or_before(date.today())
    await provider.rate_on_or_before(date.today())
    assert len(calls) == 2


@pytest.mark.parametrize("status", [500, 404])
async def test_provider_returns_none_when_source_fails(
    monkeypatch: pytest.MonkeyPatch, status: int
) -> None:
    monkeypatch.setattr(
        bcb_ptax.httpx, "AsyncClient", _client(lambda _r: httpx.Response(status, text="erro"))
    )
    provider = BcbPtaxRateProvider()
    assert await provider.rate_on_or_before(date.today() - timedelta(days=3)) is None


async def test_provider_returns_none_on_invalid_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        bcb_ptax.httpx, "AsyncClient", _client(lambda _r: httpx.Response(200, text="<html>"))
    )
    assert await BcbPtaxRateProvider().rate_on_or_before(date(2026, 10, 8)) is None
