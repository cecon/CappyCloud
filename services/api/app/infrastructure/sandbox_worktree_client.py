"""Cliente HTTP para operações git no worktree via ``session_server.js`` no sandbox.

O código anterior usava ``docker.exec_run`` a partir do processo da API. No Windows
(dev) ou quando o Docker socket não existe no host, isso falha com erros como
``FileNotFoundError`` ao ligar ao daemon — embora a sessão do agente esteja bem no
container do sandbox. Aqui o git corre **no mesmo ambiente** que o agente,
através da porta ``SANDBOX_SESSION_PORT`` (session_server).
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

log = logging.getLogger(__name__)


class SandboxWorktreeError(RuntimeError):
    """Falha ao chamar o session_server ou resposta de erro."""

    def __init__(self, message: str, *, status_code: int = 503) -> None:
        super().__init__(message)
        self.status_code = status_code


def _base_url() -> str:
    host = os.getenv("SANDBOX_HOST", "cappycloud-sandbox")
    port = os.getenv("SANDBOX_SESSION_PORT", "8080")
    return f"http://{host}:{port}"


async def _post_json(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    url = f"{_base_url()}{path}"
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
            r = await client.post(url, json=payload)
    except httpx.ConnectError as exc:
        raise SandboxWorktreeError(
            "Não foi possível ligar ao session_server do sandbox em "
            f"{_base_url()}. Defina SANDBOX_HOST / SANDBOX_SESSION_PORT e confirme "
            "que o container do sandbox está acessível a partir da API "
            f"(o Docker local na máquina da API não é necessário). Erro: {exc}",
        ) from exc
    except httpx.RequestError as exc:
        raise SandboxWorktreeError(f"Pedido ao sandbox falhou: {exc}") from exc

    try:
        data = r.json()
    except Exception:
        data = {}

    if r.status_code < 400:
        return data if isinstance(data, dict) else {}

    detail_any = data.get("detail") if isinstance(data, dict) else None
    err_any = data.get("error") if isinstance(data, dict) else None
    detail = (
        detail_any
        if isinstance(detail_any, str)
        else (err_any if isinstance(err_any, str) else None)
    ) or (r.text[:800] if r.text else "")
    raise SandboxWorktreeError(detail or f"HTTP {r.status_code}", status_code=r.status_code)


async def worktree_ls_files(worktree_path: str) -> tuple[str, list[str]]:
    data = await _post_json("/worktree/ls-files", {"worktree_path": worktree_path})
    raw = data.get("files")
    files = [f for f in raw if isinstance(f, str) and f.strip()] if isinstance(raw, list) else []
    wt = str(data.get("worktree_path") or worktree_path).strip()
    return wt, files


async def worktree_read_file(worktree_path: str, rel_path: str) -> tuple[str, str]:
    payload = {"worktree_path": worktree_path, "path": rel_path}
    data = await _post_json("/worktree/read-file", payload)
    return str(data.get("path") or rel_path), str(data.get("content") or "")


async def worktree_diff_against_base(worktree_path: str, base_branch: str) -> str:
    data = await _post_json(
        "/worktree/diff",
        {"worktree_path": worktree_path, "base_branch": base_branch},
    )
    return str(data.get("diff_text") or "")


async def worktree_push_origin_head_best_effort(worktree_path: str) -> None:
    try:
        await _post_json("/worktree/push-origin-head", {"worktree_path": worktree_path})
    except SandboxWorktreeError:
        log.warning("push-origin-head no sandbox falhou (fluxo PR pode continuar)", exc_info=True)


async def worktree_current_branch(worktree_path: str) -> str:
    data = await _post_json("/worktree/current-branch", {"worktree_path": worktree_path})
    branch = str(data.get("branch") or "").strip()
    if not branch:
        raise SandboxWorktreeError("Branch actual vazio no sandbox.")
    return branch


async def resolve_head_branch_for_pr(worktree_path: str) -> str:
    """Igual ao fluxo antigo com Docker: push best-effort + rev-parse."""
    await worktree_push_origin_head_best_effort(worktree_path)
    return await worktree_current_branch(worktree_path)
