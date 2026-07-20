"""HTTP helpers for the sandbox session sidecar."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any

from app.domain.entities import ContainerStatus, Sandbox
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
                if data.get("openclaude") == "stopped":
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
