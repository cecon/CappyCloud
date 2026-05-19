"""Unit tests for AI model tier derivation."""

from __future__ import annotations

from app.adapters.primary.http.ai_models import _derive_tier


class TestDeriveTier:
    def test_positive_price_is_paid(self) -> None:
        assert _derive_tier(2.0, 8.0) == "paid"

    def test_zero_prices_are_free(self) -> None:
        assert _derive_tier(0.0, 0.0) == "free"

    def test_missing_prices_are_unknown(self) -> None:
        assert _derive_tier(None, None) == "unknown"
