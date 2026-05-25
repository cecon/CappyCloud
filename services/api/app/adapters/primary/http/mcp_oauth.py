"""OAuth discovery and authorization endpoints for remote MCP clients."""

from __future__ import annotations

import base64
import logging
from typing import Annotated, Any
from urllib.parse import parse_qs, unquote_plus, urlsplit

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

from app.adapters.primary.http.deps import get_user_mcp_repo
from app.adapters.primary.http.mcp_oauth_views import render_authorize_form
from app.application.use_cases.mcp_oauth import (
    DEFAULT_TOKEN_ENDPOINT_AUTH_METHOD,
    OAUTH_SCOPE,
    SUPPORTED_TOKEN_ENDPOINT_AUTH_METHODS,
    McpOAuthError,
    McpOAuthService,
)
from app.application.use_cases.mcp_oauth_clients import (
    server_id_from_static_client_id,
    static_redirect_allowed,
)
from app.infrastructure.config import get_settings
from app.ports.mcp_repository import UserMcpServerRepository

router = APIRouter(tags=["mcp-oauth"])
log = logging.getLogger(__name__)


def _base_url(request: Request) -> str:
    host = request.headers.get("x-forwarded-host") or request.headers.get("host", "")
    proto = request.headers.get("x-forwarded-proto") or request.url.scheme
    return f"{proto}://{host}".rstrip("/")


def _service(repo: UserMcpServerRepository) -> McpOAuthService:
    settings = get_settings()
    return McpOAuthService(
        repo,
        secret=settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


def _auth_server_metadata(base_url: str) -> dict[str, Any]:
    return {
        "issuer": base_url,
        "authorization_endpoint": f"{base_url}/api/mcp/oauth/authorize",
        "token_endpoint": f"{base_url}/api/mcp/oauth/token",
        "registration_endpoint": f"{base_url}/api/mcp/oauth/register",
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code"],
        "code_challenge_methods_supported": ["S256"],
        "token_endpoint_auth_methods_supported": list(SUPPORTED_TOKEN_ENDPOINT_AUTH_METHODS),
        "scopes_supported": [OAUTH_SCOPE],
    }


def _resource_metadata(base_url: str, resource_path: str = "") -> dict[str, Any]:
    resource_path = resource_path.strip("/")
    resource = f"{base_url}/{resource_path}" if resource_path else f"{base_url}/api/mcp"
    return {
        "resource": resource,
        "authorization_servers": [base_url],
        "bearer_methods_supported": ["header"],
        "resource_documentation": f"{base_url}/api/mcp",
        "scopes_supported": [OAUTH_SCOPE],
    }


def _is_tokenized_mcp_resource(resource_path: str) -> bool:
    return resource_path.strip("/").startswith("api/mcp/token/")


@router.get("/.well-known/oauth-authorization-server")
async def oauth_authorization_server_metadata(request: Request) -> dict[str, Any]:
    return _auth_server_metadata(_base_url(request))


@router.head("/.well-known/oauth-authorization-server")
async def oauth_authorization_server_metadata_head() -> Response:
    return Response(status_code=status.HTTP_200_OK)


@router.get("/.well-known/openid-configuration")
async def openid_configuration(request: Request) -> dict[str, Any]:
    return _auth_server_metadata(_base_url(request))


@router.head("/.well-known/openid-configuration")
async def openid_configuration_head() -> Response:
    return Response(status_code=status.HTTP_200_OK)


@router.get("/.well-known/oauth-protected-resource")
async def oauth_protected_resource_metadata(request: Request) -> dict[str, Any]:
    return _resource_metadata(_base_url(request))


@router.head("/.well-known/oauth-protected-resource")
async def oauth_protected_resource_metadata_head() -> Response:
    return Response(status_code=status.HTTP_200_OK)


@router.get("/.well-known/oauth-protected-resource/{resource_path:path}", response_model=None)
async def oauth_protected_resource_metadata_for_path(
    request: Request,
    resource_path: str,
) -> dict[str, Any] | Response:
    if _is_tokenized_mcp_resource(resource_path):
        return Response(status_code=status.HTTP_404_NOT_FOUND)
    return _resource_metadata(_base_url(request), resource_path)


@router.head("/.well-known/oauth-protected-resource/{resource_path:path}")
async def oauth_protected_resource_metadata_for_path_head(resource_path: str) -> Response:
    if _is_tokenized_mcp_resource(resource_path):
        return Response(status_code=status.HTTP_404_NOT_FOUND)
    return Response(status_code=status.HTTP_200_OK)


@router.post(
    "/api/mcp/oauth/register",
    status_code=status.HTTP_201_CREATED,
    response_model=None,
)
async def register_oauth_client(
    request: Request,
    repo: Annotated[UserMcpServerRepository, Depends(get_user_mcp_repo)],
) -> dict[str, Any] | JSONResponse:
    payload = await request.json()
    redirect_uris = payload.get("redirect_uris") or []
    if not isinstance(redirect_uris, list):
        return _oauth_json_error("invalid_client_metadata", "redirect_uris inválido.", 400)
    client_name = str(payload.get("client_name") or payload.get("client_uri") or "Claude")
    token_endpoint_auth_method = str(
        payload.get("token_endpoint_auth_method") or DEFAULT_TOKEN_ENDPOINT_AUTH_METHOD
    )
    try:
        return _service(repo).register_client(
            redirect_uris=[str(uri) for uri in redirect_uris],
            client_name=client_name,
            token_endpoint_auth_method=token_endpoint_auth_method,
        )
    except McpOAuthError as exc:
        return _oauth_json_error("invalid_client_metadata", str(exc), 400)


@router.get("/api/mcp/oauth/authorize", response_model=None)
async def authorize_form(
    request: Request,
    repo: Annotated[UserMcpServerRepository, Depends(get_user_mcp_repo)],
) -> HTMLResponse | RedirectResponse | JSONResponse:
    params = dict(request.query_params)
    if _should_auto_authorize_static_client(params):
        log.info(
            "MCP OAuth authorize auto redirect resource_present=%s ua=%s",
            bool(params.get("resource")),
            request.headers.get("user-agent", ""),
        )
        return await _authorize_redirect(params, request=request, repo=repo)
    return HTMLResponse(render_authorize_form(params))


@router.post("/api/mcp/oauth/authorize", response_model=None)
async def authorize_submit(
    request: Request,
    repo: Annotated[UserMcpServerRepository, Depends(get_user_mcp_repo)],
) -> RedirectResponse | JSONResponse:
    form = await _read_form_urlencoded(request)
    log.info(
        "MCP OAuth authorize submit resource_present=%s token_present=%s ua=%s",
        bool(form.get("resource")),
        bool(form.get("mcp_token")),
        request.headers.get("user-agent", ""),
    )
    return await _authorize_redirect(form, request=request, repo=repo)


async def _authorize_redirect(
    form: dict[str, str],
    *,
    request: Request,
    repo: UserMcpServerRepository,
) -> RedirectResponse | JSONResponse:
    try:
        redirect_to = await _service(repo).authorize(
            response_type=form.get("response_type", ""),
            client_id=form.get("client_id", ""),
            redirect_uri=form.get("redirect_uri", ""),
            state=form.get("state", ""),
            resource=form.get("resource", ""),
            default_resource_origin=_base_url(request),
            code_challenge=form.get("code_challenge", ""),
            code_challenge_method=form.get("code_challenge_method", ""),
            mcp_token=form.get("mcp_token", ""),
        )
    except McpOAuthError as exc:
        return _oauth_json_error("access_denied", str(exc), 400)
    return _redirect_to_oauth_client(redirect_to, state=form.get("state", ""))


def _redirect_to_oauth_client(redirect_to: str, *, state: str) -> RedirectResponse:
    parsed_redirect = urlsplit(redirect_to)
    log.info(
        "MCP OAuth authorize redirect host=%s path=%s state_present=%s",
        parsed_redirect.netloc,
        parsed_redirect.path,
        bool(state),
    )
    return RedirectResponse(redirect_to, status_code=status.HTTP_303_SEE_OTHER)


def _should_auto_authorize_static_client(params: dict[str, str]) -> bool:
    return (
        params.get("response_type") == "code"
        and server_id_from_static_client_id(params.get("client_id", "")) is not None
        and static_redirect_allowed(params.get("redirect_uri", ""))
    )


@router.post("/api/mcp/oauth/token", response_model=None)
async def exchange_token(
    request: Request,
    repo: Annotated[UserMcpServerRepository, Depends(get_user_mcp_repo)],
) -> dict[str, Any] | JSONResponse:
    form = await _read_form_urlencoded(request)
    service = _service(repo)
    try:
        client_id, client_secret = _client_credentials(form, request.headers.get("authorization"))
        log.info(
            "MCP OAuth token request grant=%s basic=%s resource_present=%s ua=%s",
            form.get("grant_type", ""),
            bool(request.headers.get("authorization")),
            bool(form.get("resource")),
            request.headers.get("user-agent", ""),
        )
        if form.get("grant_type", "") == "refresh_token":
            return _oauth_token_response(
                await service.refresh_access_token(
                    grant_type=form.get("grant_type", ""),
                    refresh_token=form.get("refresh_token", ""),
                    client_id=client_id,
                    client_secret=client_secret,
                )
            )
        return _oauth_token_response(
            await service.exchange_code(
                grant_type=form.get("grant_type", ""),
                code=form.get("code", ""),
                client_id=client_id,
                client_secret=client_secret,
                redirect_uri=form.get("redirect_uri", ""),
                resource=form.get("resource", ""),
                code_verifier=form.get("code_verifier", ""),
            )
        )
    except McpOAuthError as exc:
        return _oauth_json_error("invalid_grant", str(exc), 400)


async def _read_form_urlencoded(request: Request) -> dict[str, str]:
    raw = (await request.body()).decode("utf-8")
    parsed = parse_qs(raw, keep_blank_values=True)
    return {key: values[-1] if values else "" for key, values in parsed.items()}


def _client_credentials(form: dict[str, str], authorization: str | None) -> tuple[str, str]:
    if authorization and authorization.lower().startswith("basic "):
        encoded = authorization.split(" ", 1)[1].strip()
        try:
            decoded = base64.b64decode(encoded).decode("utf-8")
        except (ValueError, UnicodeDecodeError) as exc:
            raise McpOAuthError("client authentication inválida.") from exc
        client_id, sep, client_secret = decoded.partition(":")
        if not sep:
            raise McpOAuthError("client authentication inválida.")
        return unquote_plus(client_id), unquote_plus(client_secret)
    return form.get("client_id", ""), form.get("client_secret", "")


def _oauth_json_error(error: str, description: str, status_code: int) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": error, "error_description": description},
    )


def _oauth_token_response(content: dict[str, Any]) -> JSONResponse:
    response_content = {
        "access_token": content["access_token"],
        "token_type": content["token_type"],
        "expires_in": content["expires_in"],
        "scope": content["scope"],
    }
    log.info(
        "MCP OAuth token response token_type=%s keys=%s",
        response_content["token_type"],
        ",".join(sorted(response_content.keys())),
    )
    return JSONResponse(
        content=response_content,
        headers={"Cache-Control": "no-store", "Pragma": "no-cache"},
    )
