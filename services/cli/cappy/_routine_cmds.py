"""CLI commands for routines."""

from __future__ import annotations

from typing import Optional

import typer

routine_app = typer.Typer(help="Gestão de routines (automações).")


def _client():
    from cappy.main import client

    return client()


def _err(msg: str) -> None:
    from cappy.main import err

    err(msg)


def _print(data) -> None:
    from cappy.main import print_json

    print_json(data)


@routine_app.command("list")
def routine_list() -> None:
    """Lista todas as routines."""
    with _client() as c:
        resp = c.get("/api/routines")
        if resp.status_code != 200:
            _err(f"Erro: {resp.text}")
    _print(resp.json())


@routine_app.command("create")
def routine_create(
    name: str = typer.Option(..., "--name", help="Nome da routine"),
    env_slug: str = typer.Option(..., "--env", help="Slug do ambiente"),
    prompt: str = typer.Option(..., "--prompt", help="Instrução para o agente"),
    schedule: Optional[str] = typer.Option(
        None, "--schedule", help="Cron expression (ex: '0 9 * * 1-5')"
    ),
) -> None:
    """Cria uma nova routine."""
    triggers = []
    if schedule:
        triggers.append({"type": "schedule", "config": {"cron": schedule}})
    triggers.append({"type": "api", "config": {}})

    with _client() as c:
        resp = c.post(
            "/api/routines",
            json={
                "name": name,
                "env_slug": env_slug,
                "prompt": prompt,
                "triggers": triggers,
                "enabled": True,
            },
        )
        if resp.status_code not in (200, 201):
            _err(f"Erro: {resp.text}")
    data = resp.json()
    typer.echo(f"✓ Routine criada: {data.get('id')} — {data.get('name')}")


@routine_app.command("run")
def routine_run(
    routine_id: str = typer.Argument(..., help="UUID da routine"),
) -> None:
    """Disparo manual de uma routine."""
    with _client() as c:
        resp = c.post(f"/api/routines/{routine_id}/run")
        if resp.status_code not in (200, 201):
            _err(f"Erro: {resp.text}")
    data = resp.json()
    typer.echo(
        f"✓ Run disparado: task_id={data.get('task_id')}, run_id={data.get('run_id')}"
    )


@routine_app.command("logs")
def routine_logs(
    routine_id: str = typer.Argument(..., help="UUID da routine"),
) -> None:
    """Historial de execuções de uma routine."""
    with _client() as c:
        resp = c.get(f"/api/routines/{routine_id}/runs")
        if resp.status_code != 200:
            _err(f"Erro: {resp.text}")
    _print(resp.json())
