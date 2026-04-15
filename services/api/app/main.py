"""Aplicação FastAPI CappyCloud — auth, conversas e agente."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import cors_origins_list, get_settings
from app.database import init_db
from app.routers import auth, conversations
from cappycloud_agent import Pipeline


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Arranca o pipeline do agente e a base de dados."""
    await init_db()
    pipeline = Pipeline()
    await pipeline.on_startup()
    app.state.pipeline = pipeline
    yield
    await pipeline.on_shutdown()


settings = get_settings()
app = FastAPI(title=settings.app_name, lifespan=lifespan)


def _pt_validation_msg(err: dict) -> str:
    """Traduz mensagens típicas do Pydantic para português (422)."""
    msg = str(err.get("msg", ""))
    if msg.startswith("Value error, "):
        msg = msg[len("Value error, ") :].strip()
    typ = str(err.get("type", ""))
    loc = err.get("loc") or []
    loc_s = ".".join(str(x) for x in loc if x != "body")

    if typ == "missing":
        return f"Campo em falta: {loc_s or 'pedido'}."

    if loc and loc[-1] == "email":
        if "password" not in msg.lower() and ("@" in msg or "email" in msg.lower() or typ == "value_error"):
            return "Email inválido. Use um endereço completo (ex.: nome@servidor.com)."

    if loc and loc[-1] == "password":
        if "at least" in msg.lower() or typ == "string_too_short":
            return "A password deve ter pelo menos 8 caracteres."
        if msg:
            return msg

    return msg or "Dados do formulário inválidos."


@app.exception_handler(RequestValidationError)
async def request_validation_exception_handler(
    _request, exc: RequestValidationError
) -> JSONResponse:
    """422 com `detail[].msg` legível em PT (o browser ainda mostra 422 na rede — é normal)."""
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

app.include_router(auth.router, prefix="/api")
app.include_router(conversations.router, prefix="/api")


@app.get("/health")
async def health():
    """Healthcheck para orquestração (Docker / k8s)."""
    return {"status": "ok"}
