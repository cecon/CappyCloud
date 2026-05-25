"""HTTP JSON-RPC endpoint implementing repository MCP tools."""

from __future__ import annotations

import logging
import uuid
from json import JSONDecodeError
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse

from app.adapters.primary.http.deps import (
    get_repository_mcp_tool_gateway,
    get_user_mcp_repo,
)
from app.adapters.secondary.mcp_telemetry_recorder import schedule_mcp_tool_invocation
from app.application.use_cases.mcp_oauth import McpOAuthError, McpOAuthService
from app.application.use_cases.mcp_telemetry import (
    TelemetryRecorder,
    caller_session_id,
    resolve_trace_id,
)
from app.application.use_cases.repository_mcp import (
    HandleRepositoryMcpRequest,
    RepositoryMcpAuthError,
)
from app.infrastructure.config import get_settings
from app.ports.mcp_repository import UserMcpServerRepository
from app.ports.repository_mcp import RepositoryMcpToolGateway

router = APIRouter(prefix="/mcp", tags=["mcp"])
log = logging.getLogger(__name__)


def get_mcp_telemetry_recorder() -> TelemetryRecorder:
    return schedule_mcp_tool_invocation


def _extract_token(
    authorization: str | None,
    header_token: str | None,
    query_token: str | None,
) -> str:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    if header_token:
        return header_token.strip()
    if query_token:
        return query_token.strip()
    return ""


def _base_url(request: Request) -> str:
    host = request.headers.get("x-forwarded-host") or request.headers.get("host", "")
    proto = request.headers.get("x-forwarded-proto") or request.url.scheme
    return f"{proto}://{host}".rstrip("/")


def _auth_headers(request: Request, server_id: uuid.UUID) -> dict[str, str]:
    metadata = (
        f"{_base_url(request)}/.well-known/oauth-protected-resource/api/mcp/servers/{server_id}"
    )
    return {
        "WWW-Authenticate": (
            'Bearer realm="cappycloud-mcp", error="invalid_token", '
            f'resource_metadata="{metadata}", scope="repository:read"'
        )
    }


def _oauth_service(repo: UserMcpServerRepository) -> McpOAuthService:
    settings = get_settings()
    return McpOAuthService(repo, secret=settings.jwt_secret, algorithm=settings.jwt_algorithm)


@router.get("/servers/{server_id}")
async def repository_mcp_get_endpoint(
    server_id: uuid.UUID,
    request: Request,
    repo: Annotated[UserMcpServerRepository, Depends(get_user_mcp_repo)],
    authorization: Annotated[str | None, Header()] = None,
    x_cappycloud_mcp_token: Annotated[str | None, Header()] = None,
) -> Response:
    trace_id = resolve_trace_id(request.headers)
    request.state.trace_id = trace_id
    query_token = (
        request.query_params.get("mcp_token")
        or request.query_params.get("token")
        or request.query_params.get("access_token")
    )
    token = _extract_token(authorization, x_cappycloud_mcp_token, query_token)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token MCP ausente.",
            headers=_auth_headers(request, server_id),
        )
    try:
        await _oauth_service(repo).resolve_bearer_token(server_id=server_id, token=token)
    except McpOAuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers=_auth_headers(request, server_id),
        ) from exc
    log.info(
        "MCP GET stream probe bearer=%s query_token=%s ua=%s",
        bool(authorization),
        bool(query_token),
        request.headers.get("user-agent", ""),
    )
    return Response(
        status_code=status.HTTP_405_METHOD_NOT_ALLOWED,
        headers={"Allow": "POST", "X-Request-Id": str(trace_id)},
    )


@router.head("/servers/{server_id}")
async def probe_mcp_server(server_id: uuid.UUID, request: Request) -> Response:
    trace_id = resolve_trace_id(request.headers)
    return Response(
        status_code=status.HTTP_401_UNAUTHORIZED,
        headers={**_auth_headers(request, server_id), "X-Request-Id": str(trace_id)},
    )


@router.post("/servers/{server_id}", response_model=None)
async def repository_mcp_endpoint(
    server_id: uuid.UUID,
    request: Request,
    repo: Annotated[UserMcpServerRepository, Depends(get_user_mcp_repo)],
    gateway: Annotated[RepositoryMcpToolGateway, Depends(get_repository_mcp_tool_gateway)],
    telemetry_recorder: Annotated[TelemetryRecorder, Depends(get_mcp_telemetry_recorder)],
    authorization: Annotated[str | None, Header()] = None,
    x_cappycloud_mcp_token: Annotated[str | None, Header()] = None,
) -> Response | dict[str, Any] | list[dict[str, Any]]:
    telemetry_context = _telemetry_context(request)
    query_token = (
        request.query_params.get("mcp_token")
        or request.query_params.get("token")
        or request.query_params.get("access_token")
    )
    token = _extract_token(authorization, x_cappycloud_mcp_token, query_token)
    return await _handle_repository_mcp(
        server_id=server_id,
        request=request,
        repo=repo,
        gateway=gateway,
        telemetry_recorder=telemetry_recorder,
        telemetry_context=telemetry_context,
        token=token,
        has_bearer=bool(authorization),
        has_query_token=bool(query_token),
    )


@router.head("/token/{mcp_token}/servers/{server_id}")
async def probe_tokenized_mcp_server(mcp_token: str, server_id: uuid.UUID) -> Response:
    _ = (mcp_token, server_id)
    return Response(status_code=status.HTTP_200_OK)


@router.post("/token/{mcp_token}/servers/{server_id}", response_model=None)
async def tokenized_repository_mcp_endpoint(
    mcp_token: str,
    server_id: uuid.UUID,
    request: Request,
    repo: Annotated[UserMcpServerRepository, Depends(get_user_mcp_repo)],
    gateway: Annotated[RepositoryMcpToolGateway, Depends(get_repository_mcp_tool_gateway)],
    telemetry_recorder: Annotated[TelemetryRecorder, Depends(get_mcp_telemetry_recorder)],
) -> Response | dict[str, Any] | list[dict[str, Any]]:
    telemetry_context = _telemetry_context(request)
    return await _handle_repository_mcp(
        server_id=server_id,
        request=request,
        repo=repo,
        gateway=gateway,
        telemetry_recorder=telemetry_recorder,
        telemetry_context=telemetry_context,
        token=mcp_token,
        has_bearer=False,
        has_query_token=False,
    )


async def _handle_repository_mcp(
    *,
    server_id: uuid.UUID,
    request: Request,
    repo: UserMcpServerRepository,
    gateway: RepositoryMcpToolGateway,
    telemetry_recorder: TelemetryRecorder,
    telemetry_context: dict[str, Any],
    token: str,
    has_bearer: bool,
    has_query_token: bool,
) -> Response | dict[str, Any] | list[dict[str, Any]]:
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token MCP ausente.",
            headers={
                **_auth_headers(request, server_id),
                "X-Request-Id": str(telemetry_context["trace_id"]),
            },
        )
    try:
        body = await request.json()
    except JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="JSON-RPC inválido.") from exc
    _log_mcp_request(
        request,
        body,
        has_bearer=has_bearer,
        has_query_token=has_query_token,
    )
    handler = HandleRepositoryMcpRequest(repo, gateway, telemetry_recorder)
    try:
        server = await _oauth_service(repo).resolve_bearer_token(server_id=server_id, token=token)
        if isinstance(body, list):
            responses = []
            for item in body:
                if not isinstance(item, dict):
                    continue
                response = await handler.execute_for_server(
                    server=server,
                    message=item,
                    telemetry_context=telemetry_context,
                )
                if response is not None:
                    responses.append(response)
            payload: Response | list[dict[str, Any]]
            payload = responses if responses else Response(status_code=status.HTTP_202_ACCEPTED)
            return _with_trace_header(payload, telemetry_context["trace_id"])
        if not isinstance(body, dict):
            raise HTTPException(status_code=400, detail="JSON-RPC inválido.")
        response = await handler.execute_for_server(
            server=server,
            message=body,
            telemetry_context=telemetry_context,
        )
    except (RepositoryMcpAuthError, McpOAuthError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={
                **_auth_headers(request, server_id),
                "X-Request-Id": str(telemetry_context["trace_id"]),
            },
        ) from exc
    if response is None:
        return _with_trace_header(
            Response(status_code=status.HTTP_202_ACCEPTED), telemetry_context["trace_id"]
        )
    return _with_trace_header(response or {}, telemetry_context["trace_id"])


def _log_mcp_request(
    request: Request,
    body: Any,
    *,
    has_bearer: bool,
    has_query_token: bool,
) -> None:
    method = ""
    if isinstance(body, dict):
        method = str(body.get("method") or "")
    elif isinstance(body, list):
        method = ",".join(str(item.get("method") or "") for item in body if isinstance(item, dict))
    log.info(
        "MCP request method=%s bearer=%s query_token=%s ua=%s",
        method,
        has_bearer,
        has_query_token,
        request.headers.get("user-agent", ""),
    )


def _telemetry_context(request: Request) -> dict[str, Any]:
    trace_id = resolve_trace_id(request.headers)
    request.state.trace_id = trace_id
    return {
        "trace_id": trace_id,
        "caller_user_agent": request.headers.get("user-agent", "")[:1000],
        "caller_session_id": caller_session_id(request.headers),
    }


def _with_trace_header(
    payload: Response | dict[str, Any] | list[dict[str, Any]],
    trace_id: uuid.UUID,
) -> Response:
    if isinstance(payload, Response):
        payload.headers["X-Request-Id"] = str(trace_id)
        return payload
    return JSONResponse(content=payload, headers={"X-Request-Id": str(trace_id)})
