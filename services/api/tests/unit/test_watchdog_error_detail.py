"""O erro do clone guardado no repositório diz o motivo real, sem credenciais."""

from __future__ import annotations

import httpx
from app.infrastructure.sandbox_watchdog import error_detail


def _status_error(status: int, **kwargs: object) -> httpx.HTTPStatusError:
    request = httpx.Request("POST", "http://sandbox:8080/repos/clone")
    response = httpx.Response(status, request=request, **kwargs)  # type: ignore[arg-type]
    return httpx.HTTPStatusError("Server error", request=request, response=response)


def test_usa_a_mensagem_do_sandbox_e_tira_o_token() -> None:
    exc = _status_error(
        500,
        json={
            "error": "fatal: could not read Username for 'https://pat:s3cr3t@dev.azure.com/seller'"
        },
    )

    detail = error_detail(exc)

    assert detail.startswith("HTTP 500: fatal: could not read Username")
    assert "s3cr3t" not in detail
    assert "https://***@dev.azure.com/seller" in detail


def test_corpo_sem_json_e_outros_erros() -> None:
    assert error_detail(_status_error(502, text="bad gateway")) == "HTTP 502: bad gateway"
    assert error_detail(httpx.ConnectError("sandbox fora")) == "sandbox fora"
