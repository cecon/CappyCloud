"""Aplicação FastAPI CappyCloud — ponto de entrada e wiring de infraestrutura."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.adapters.primary.http import auth as auth_router
from app.adapters.primary.http import conversations as conv_router
from app.adapters.primary.http import environments as env_router
from app.infrastructure.config import cors_origins_list, get_settings
from app.infrastructure.database import init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Arranca o pipeline do agente e inicializa a base de dados."""
    from app.adapters.secondary.agent.pipeline_adapter import PipelineAdapter

    await init_db()
    agent = PipelineAdapter()
    await agent.on_startup()
    app.state.agent = agent
    yield
    await agent.on_shutdown()


settings = get_settings()
app = FastAPI(title=settings.app_name, lifespan=lifespan)


def _pt_validation_msg(err: dict[str, Any]) -> str:
    """Traduz mensagens típicas do Pydantic para português (422)."""
    msg = str(err.get("msg", ""))
    if msg.startswith("Value error, "):
        msg = msg[len("Value error, ") :].strip()
    typ = str(err.get("type", ""))
    loc = err.get("loc") or []
    loc_s = ".".join(str(x) for x in loc if x != "body")

    if typ == "missing":
        return f"Campo em falta: {loc_s or 'pedido'}."
    if (
        loc
        and loc[-1] == "email"
        and "password" not in msg.lower()
        and ("@" in msg or "email" in msg.lower())
    ):
        return "Email inválido. Use um endereço completo (ex.: nome@servidor.com)."
    if loc and loc[-1] == "password":
        if "at least" in msg.lower() or typ == "string_too_short":
            return "A password deve ter pelo menos 8 caracteres."
        if msg:
            return msg
    return msg or "Dados do formulário inválidos."


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    _request: object, exc: RequestValidationError
) -> JSONResponse:
    """422 com detail legível em português."""
    out = []
    for e in exc.errors():
        row = dict(e) if isinstance(e, dict) else {"msg": str(e)}
        out.append(
            {
                "type": row.get("type"),
                "loc": list(row.get("loc", ())),
                "msg": _pt_validation_msg(row),
            }
        )
    return JSONResponse(status_code=422, content={"detail": out})


app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins_list(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router.router, prefix="/api")
app.include_router(conv_router.router, prefix="/api")
app.include_router(env_router.router, prefix="/api")


@app.get("/health")
async def health() -> dict[str, str]:
    """Healthcheck para orquestração (Docker / k8s)."""
    return {"status": "ok"}
