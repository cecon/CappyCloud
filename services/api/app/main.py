"""Aplicação FastAPI CappyCloud — ponto de entrada e wiring de infraestrutura."""

from __future__ import annotations

import logging
import re
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from app.adapters.primary.http import admin_ai_catalog as admin_ai_catalog_router
from app.adapters.primary.http import admin_mcp_telemetry as admin_mcp_telemetry_router
from app.adapters.primary.http import admin_sandbox_globals as admin_sandbox_globals_router
from app.adapters.primary.http import admin_sandbox_mcps as admin_sandbox_mcps_router
from app.adapters.primary.http import admin_sandboxes as admin_sandboxes_router
from app.adapters.primary.http import admin_user_access as admin_user_access_router
from app.adapters.primary.http import admin_users as admin_users_router
from app.adapters.primary.http import ai_models as ai_models_router
from app.adapters.primary.http import attachments as attachments_router
from app.adapters.primary.http import auth as auth_router
from app.adapters.primary.http import conversation_diff as conv_diff_router
from app.adapters.primary.http import conversation_commands as conv_commands_router
from app.adapters.primary.http import conversation_files as conv_files_router
from app.adapters.primary.http import conversation_pr as conv_pr_router
from app.adapters.primary.http import conversations as conv_router
from app.adapters.primary.http import document_graph as document_graph_router
from app.adapters.primary.http import documents as documents_router
from app.adapters.primary.http import environments as env_router
from app.adapters.primary.http import git_providers as git_providers_router
from app.adapters.primary.http import mcp_oauth as mcp_oauth_router
from app.adapters.primary.http import repositories_admin as repos_admin_router
from app.adapters.primary.http import repository_mcp as repository_mcp_router
from app.adapters.primary.http import routines as routines_router
from app.adapters.primary.http import sandboxes as sandboxes_router
from app.adapters.primary.http import skills as skills_router
from app.adapters.primary.http import skills_search as skills_search_router
from app.adapters.primary.http import tasks as tasks_router
from app.adapters.primary.http import user_mcp_servers as user_mcp_servers_router
from app.adapters.primary.http import user_preferences as user_preferences_router
from app.adapters.primary.http import user_workspaces as user_workspaces_router
from app.adapters.primary.http import webhooks as webhooks_router
from app.adapters.primary.http import workspaces as workspaces_router
from app.infrastructure.config import cors_origins_list, get_settings
from app.infrastructure.database import init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger(__name__)
_MCP_TOKEN_RE = re.compile(r"cappy_mcp_[A-Za-z0-9_-]+")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Arranca o pipeline do agente, APScheduler e inicializa a base de dados."""
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

    from app.adapters.secondary.agent.pipeline_adapter import PipelineAdapter

    await init_db()

    from app.infrastructure.database import async_session_factory
    from app.infrastructure.first_admin_bootstrap import ensure_first_admin

    await ensure_first_admin(get_settings(), async_session_factory)

    agent = PipelineAdapter()
    await agent.on_startup()
    app.state.agent = agent

    from app.adapters.secondary.mcp_telemetry_recorder import prune_mcp_invocations
    from app.infrastructure.sandbox_watchdog import SandboxWatchdog

    scheduler = AsyncIOScheduler()
    watchdog = SandboxWatchdog(async_session_factory)
    scheduler.add_job(watchdog.run_once, "interval", seconds=10, id="sandbox_watchdog")
    scheduler.add_job(
        prune_mcp_invocations,
        "interval",
        days=1,
        id="mcp_telemetry_prune",
        kwargs={"retention_days": settings.mcp_telemetry_retention_days},
    )
    scheduler.start()
    app.state.scheduler = scheduler

    yield

    scheduler.shutdown(wait=False)
    await agent.on_shutdown()


settings = get_settings()
app = FastAPI(title=settings.app_name, lifespan=lifespan)


def _is_mcp_diagnostic_path(path: str) -> bool:
    return (
        path.startswith("/api/mcp")
        or path.startswith("/mcp")
        or path.startswith("/.well-known/oauth")
        or path.startswith("/.well-known/openid-configuration")
    )


def _sanitize_mcp_path(path: str) -> str:
    return _MCP_TOKEN_RE.sub("cappy_mcp_***", path)


@app.middleware("http")
async def log_unmapped_mcp_routes(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    response = await call_next(request)
    if response.status_code in {404, 405} and _is_mcp_diagnostic_path(request.url.path):
        query_keys = ",".join(sorted(request.query_params.keys())) or "-"
        log.info(
            "MCP route miss status=%s method=%s path=%s query_keys=%s ua=%s",
            response.status_code,
            request.method,
            _sanitize_mcp_path(request.url.path),
            query_keys,
            request.headers.get("user-agent", ""),
        )
    return response


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
app.include_router(admin_users_router.router, prefix="/api")
app.include_router(admin_mcp_telemetry_router.router, prefix="/api")
app.include_router(admin_sandboxes_router.router, prefix="/api")
app.include_router(admin_user_access_router.router, prefix="/api")
app.include_router(admin_ai_catalog_router.router, prefix="/api")
app.include_router(attachments_router.router)
app.include_router(conv_router.router, prefix="/api")
app.include_router(conv_commands_router.router, prefix="/api")
app.include_router(conv_diff_router.router, prefix="/api")
app.include_router(conv_files_router.router, prefix="/api")
app.include_router(conv_pr_router.router, prefix="/api")
app.include_router(env_router.router, prefix="/api")
app.include_router(routines_router.router, prefix="/api")
app.include_router(tasks_router.router, prefix="/api")
app.include_router(webhooks_router.router, prefix="/api")
app.include_router(sandboxes_router.router, prefix="/api")
app.include_router(workspaces_router.router, prefix="/api")
app.include_router(git_providers_router.router, prefix="/api")
app.include_router(ai_models_router.router, prefix="/api")
app.include_router(repos_admin_router.router, prefix="/api")
app.include_router(user_preferences_router.router, prefix="/api")
app.include_router(user_workspaces_router.router, prefix="/api")
app.include_router(user_mcp_servers_router.router, prefix="/api")
app.include_router(repository_mcp_router.router, prefix="/api")
app.include_router(documents_router.router, prefix="/api")
app.include_router(document_graph_router.router, prefix="/api")
app.include_router(skills_router.router, prefix="/api")
app.include_router(skills_search_router.router, prefix="/api")
app.include_router(admin_sandbox_mcps_router.router, prefix="/api")
app.include_router(admin_sandbox_globals_router.global_skills_router, prefix="/api")
app.include_router(admin_sandbox_globals_router.skills_router, prefix="/api")
app.include_router(admin_sandbox_globals_router.agents_router, prefix="/api")
app.include_router(mcp_oauth_router.router)


@app.get("/health")
async def health() -> dict[str, str]:
    """Healthcheck para orquestração (Docker / k8s)."""
    return {"status": "ok"}
