"""Custo do openclaude: leitura e gravação de cache não saem a preço cheio."""

from __future__ import annotations

import pytest
from app.application.use_cases._stream_helpers import compute_cost


class _Pricing:
    async def get_model_pricing(self, model_used: str) -> tuple[float, float] | None:
        return (4.0, 20.0) if model_used == "claude-opus-5-5" else None


# Caso real (chamado 30537062, 09/11): a Cappy mostrou US$ 6,24 cobrando tudo como input.
_USAGE = {
    "model_used": "claude-opus-5-5",
    "prompt_tokens": 1_528_472,
    "completion_tokens": 6_486,
    "cache_read_tokens": 1_407_421,
    "cache_write_tokens": 121_021,
}


async def test_cache_e_precificado_pelo_preco_dele() -> None:
    cost = await compute_cost(_Pricing(), _USAGE)  # type: ignore[arg-type]

    # 30 novos x 4 + 1.407.421 x 0,2 (Opus 5.5 lê cache a 0,05x) + 121.021 x 5
    # + 6.486 x 20, por milhão.
    assert cost == pytest.approx(1.016429, abs=1e-6)


async def test_sem_parcelas_de_cache_cobra_o_input_inteiro() -> None:
    usage = {k: v for k, v in _USAGE.items() if not k.startswith("cache_")}

    assert await compute_cost(_Pricing(), usage) == pytest.approx(6.243608)  # type: ignore[arg-type]


async def test_outros_modelos_leem_cache_a_um_decimo() -> None:
    class _Sonnet:
        async def get_model_pricing(self, model_used: str) -> tuple[float, float]:
            return (2.0, 10.0)

    usage = {
        "model_used": "claude-sonnet-5-5",
        "prompt_tokens": 10_000,
        "cache_read_tokens": 10_000,
    }

    assert await compute_cost(_Sonnet(), usage) == pytest.approx(0.002)  # type: ignore[arg-type]
