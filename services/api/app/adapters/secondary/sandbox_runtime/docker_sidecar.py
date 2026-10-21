"""HTTP helpers for the sandbox session sidecar."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any

from app.domain.entities import ContainerStatus, Sandbox
from app.domain.value_objects import AgentRuntime
from app.ports.sandbox_runtime import RuntimeFailureError, RuntimeProbe


def _int_from_health(value: Any) -> int:
    try:
        parsed = int(value)
    except TypeError, ValueError:
        return 0
    return max(0, parsed)


def _online_status_for(sandbox: Sandbox) -> ContainerStatus:
    if sandbox.container_status is ContainerStatus.CONFIGURED:
        return ContainerStatus.CONFIGURED
    return ContainerStatus.RUNNING


def probe_session_server(sandbox: Sandbox) -> RuntimeProbe | None:
    url = f"http://{sandbox.host}:{sandbox.session_port}/health"
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            if 200 <= response.status < 300:
                data = json.loads(response.read().decode("utf-8") or "{}")
                active_sessions = _int_from_health(data.get("sessions"))
                # openclaude parado só conta se é ele que atende o chat: no Claude CLI
                # esse processo é irrelevante e derrubava a sandbox para "parada".
                uses_openclaude = sandbox.agent_runtime is not AgentRuntime.CLAUDE_CLI
                if uses_openclaude and data.get("openclaude") == "stopped":
                    return RuntimeProbe(
                        status=ContainerStatus.STOPPED,
                        runtime_ref=url,
                        active_sessions=active_sessions,
                    )
                return RuntimeProbe(
                    status=_online_status_for(sandbox),
                    runtime_ref=url,
                    active_sessions=active_sessions,
                )
    except OSError, urllib.error.URLError, TimeoutError:
        return None
    return None


def fetch_claude_status(sandbox: Sandbox) -> dict[str, Any]:
    """Estado do Claude CLI no sandbox (instalado, versão, `claude login` feito).

    Nunca levanta exceção: sandbox fora do ar ou imagem antiga viram
    ``reachable=False`` com o motivo, para o admin mostrar o diagnóstico.
    """
    url = f"http://{sandbox.host}:{sandbox.session_port}/claude/status"
    request = urllib.request.Request(url, method="GET")
    request.add_header("X-Internal-Token", os.getenv("INTERNAL_API_TOKEN", "").strip())
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            data = json.loads(response.read().decode("utf-8") or "{}")
            return {"reachable": True, **data}
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return {"reachable": False, "error": "imagem do sandbox sem runtime Claude CLI"}
        return {"reachable": False, "error": f"HTTP {exc.code}"}
    except (OSError, TimeoutError, ValueError) as exc:
        return {"reachable": False, "error": str(exc)}


def post_runtime_control(sandbox: Sandbox, action: str) -> None:
    url = f"http://{sandbox.host}:{sandbox.session_port}/runtime/{action}"
    request = urllib.request.Request(url, data=b"{}", method="POST")
    request.add_header("Content-Type", "application/json")
    try:
        urllib.request.urlopen(request, timeout=5).close()
    except OSError as exc:
        raise RuntimeFailureError(
            f"Falha ao controlar OpenClaude via sidecar: {exc}",
            sandbox_id=sandbox.id,
        ) from exc


def restart_session_server(sandbox: Sandbox) -> RuntimeProbe:
    post_runtime_control(sandbox, "restart-openclaude")
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        time.sleep(1)
        probe = probe_session_server(sandbox)
        if probe is not None:
            return probe
    return RuntimeProbe(
        status=ContainerStatus.STARTING,
        runtime_ref=f"http://{sandbox.host}:{sandbox.session_port}/runtime/restart-openclaude",
        last_error="OpenClaude reiniciando; /health ainda indisponivel",
    )


def stop_session_server(sandbox: Sandbox) -> RuntimeProbe:
    post_runtime_control(sandbox, "stop-openclaude")
    return RuntimeProbe(
        status=ContainerStatus.STOPPED,
        runtime_ref=f"http://{sandbox.host}:{sandbox.session_port}/runtime/stop-openclaude",
    )
