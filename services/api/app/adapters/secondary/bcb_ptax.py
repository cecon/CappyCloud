"""Cotação PTAX (venda) do Banco Central do Brasil, via API pública Olinda.

https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/aplicacao — sem
autenticação. Cotações passadas não mudam, então ficam em memória.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any

import httpx

from app.ports.exchange_rates import ExchangeRate, UsdBrlRateProvider

log = logging.getLogger(__name__)

PTAX_URL = (
    "https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata/"
    "CotacaoDolarPeriodo(dataInicial=@dataInicial,dataFinalCotacao=@dataFinalCotacao)"
)
PTAX_SOURCE = "PTAX venda, Banco Central do Brasil"
# Feriados emendados não passam de uma semana sem cotação.
_LOOKBACK_DAYS = 10


def _bcb_date(day: date) -> str:
    return day.strftime("%m-%d-%Y")


def parse_ptax(payload: Any) -> ExchangeRate | None:
    """Último item de ``value`` (ordem crescente de data) → cotação de venda."""
    items = payload.get("value") if isinstance(payload, dict) else None
    if not items:
        return None
    last = max(items, key=lambda item: str(item.get("dataHoraCotacao", "")))
    try:
        quoted = datetime.strptime(str(last["dataHoraCotacao"])[:10], "%Y-%m-%d").date()
        return ExchangeRate(rate=float(last["cotacaoVenda"]), quoted_on=quoted, source=PTAX_SOURCE)
    except KeyError, TypeError, ValueError:
        return None


class BcbPtaxRateProvider(UsdBrlRateProvider):
    def __init__(self, timeout: float = 5.0) -> None:
        self._timeout = timeout
        self._cache: dict[date, ExchangeRate] = {}

    async def rate_on_or_before(self, day: date) -> ExchangeRate | None:
        if day in self._cache:
            return self._cache[day]
        params = {
            "@dataInicial": f"'{_bcb_date(day - timedelta(days=_LOOKBACK_DAYS))}'",
            "@dataFinalCotacao": f"'{_bcb_date(day)}'",
            "$format": "json",
        }
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(PTAX_URL, params=params)
                response.raise_for_status()
                rate = parse_ptax(response.json())
        except (httpx.HTTPError, ValueError) as exc:
            log.warning("PTAX indisponível para %s: %s", day, exc)
            return None
        # Hoje a cotação pode ainda não ter saído: só guarda dias passados.
        if rate is not None and day < date.today():
            self._cache[day] = rate
        return rate
