"""Port de cotação do dólar (US$ → R$) para relatórios."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class ExchangeRate:
    """Quantos reais vale um dólar, em que dia e segundo quem."""

    rate: float
    quoted_on: date
    source: str


class UsdBrlRateProvider(ABC):
    @abstractmethod
    async def rate_on_or_before(self, day: date) -> ExchangeRate | None:
        """Cotação do último dia útil até ``day``; ``None`` se a fonte não responder."""
