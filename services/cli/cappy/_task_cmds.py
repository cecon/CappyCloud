"""CLI commands for agent tasks."""

from __future__ import annotations

import json
from typing import Optional

import typer

task_app = typer.Typer(help="Gestão de tasks de agente.")


def _client():
    from cappy.main import client

    return client()


def _err(msg: str) -> None:
    from cappy.main import err

    err(msg)


def _print(data) -> None:
    from cappy.main import print_json

    print_json(data)


@task_app.command("list")
def task_list(
    env_slug: Optional[str] = typer.Option(None, "--env", help="Filtrar por env_slug"),
    task_status: Optional[str] = typer.Option(
        None, "--status", help="Filtrar por status"
    ),
) -> None:
    """Lista tasks de agente."""
    params = {k: v for k, v in [("env_slug", env_slug), ("status", task_status)] if v}
    with _client() as c:
        resp = c.get("/api/tasks", params=params)
        if resp.status_code != 200:
            _err(f"Erro: {resp.text}")
    _print(resp.json())


@task_app.command("trigger")
def task_trigger(
    env_slug: str = typer.Argument(..., help="Slug do ambiente alvo"),
    prompt: str = typer.Argument(..., help="Instrução para o agente"),
) -> None:
    """Dispara uma nova task de agente via CLI."""
    with _client() as c:
        resp = c.post(
            "/api/tasks",
            json={"env_slug": env_slug, "prompt": prompt, "triggered_by": "manual"},
        )
        if resp.status_code not in (200, 201):
            _err(f"Erro: {resp.text}")
    data = resp.json()
    typer.echo(f"✓ Task criada: {data.get('task_id')}")


@task_app.command("logs")
def task_logs(
    task_id: str = typer.Argument(..., help="UUID da task"),
    follow: bool = typer.Option(
        False, "--follow", "-f", help="Seguir eventos em tempo real"
    ),
) -> None:
    """Mostra os eventos de uma task."""
    with _client() as c:
        resp = c.get(f"/api/tasks/{task_id}/events")
        if resp.status_code != 200:
            _err(f"Erro: {resp.text}")
    events = resp.json()
    for ev in events:
        eid = ev.get("id", "")
        etype = ev.get("event_type", "")
        data = ev.get("data", {})
        msg = data.get("message") or data.get("content") or json.dumps(data)
        typer.echo(f"[{eid}] {etype}: {msg}")

    if follow:
        import time

        typer.echo("(--follow: polling a cada 2s, Ctrl+C para sair)")
        last_id = events[-1]["id"] if events else 0
        while True:
            time.sleep(2)
            with _client() as c2:
                resp2 = c2.get(
                    f"/api/tasks/{task_id}/events", params={"after": last_id}
                )
                if resp2.status_code != 200:
                    break
                new_evs = resp2.json()
                for ev in new_evs:
                    last_id = ev["id"]
                    data = ev.get("data", {})
                    msg = data.get("message") or data.get("content") or json.dumps(data)
                    typer.echo(f"[{last_id}] {ev.get('event_type', '')}: {msg}")
                if any(e.get("event_type") in ("done", "error") for e in new_evs):
                    break
