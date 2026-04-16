"""CLI CappyCloud (cappy) — gestão de ambientes, tasks e routines via API REST."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Optional

import httpx
import typer

app = typer.Typer(
    name="cappy",
    help="CappyCloud CLI — gere ambientes, tasks e routines.",
    no_args_is_help=True,
)

env_app = typer.Typer(help="Gestão de ambientes Docker.")
task_app = typer.Typer(help="Gestão de tasks de agente.")
routine_app = typer.Typer(help="Gestão de routines (automações).")
webhook_app = typer.Typer(help="Utilitários de webhook.")

app.add_typer(env_app, name="env")
app.add_typer(task_app, name="task")
app.add_typer(routine_app, name="routine")
app.add_typer(webhook_app, name="webhook")

_CONFIG_PATH = Path.home() / ".cappy" / "config.json"


# ── Config ────────────────────────────────────────────────────────────────────


def _load_config() -> dict:
    if _CONFIG_PATH.exists():
        return json.loads(_CONFIG_PATH.read_text())
    return {}


def _save_config(cfg: dict) -> None:
    _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    _CONFIG_PATH.write_text(json.dumps(cfg, indent=2))


def _get_api_url() -> str:
    return os.getenv("CAPPY_API_URL") or _load_config().get("api_url") or "http://localhost:8000"


def _get_token() -> str:
    return os.getenv("CAPPY_TOKEN") or _load_config().get("token") or ""


def _client() -> httpx.Client:
    token = _get_token()
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return httpx.Client(base_url=_get_api_url(), headers=headers, timeout=30)


def _print_json(data) -> None:
    typer.echo(json.dumps(data, indent=2, ensure_ascii=False, default=str))


def _err(msg: str) -> None:
    typer.echo(f"[erro] {msg}", err=True)
    raise typer.Exit(1)


# ── Configure ─────────────────────────────────────────────────────────────────


@app.command()
def configure(
    api_url: str = typer.Option(..., prompt="URL da API (ex: http://localhost:8000)"),
    email: str = typer.Option(..., prompt="Email"),
    password: str = typer.Option(..., prompt="Password", hide_input=True),
) -> None:
    """Configura credenciais para o CLI."""
    with httpx.Client(base_url=api_url, timeout=15) as c:
        resp = c.post("/api/auth/login", data={"username": email, "password": password})
        if resp.status_code != 200:
            _err(f"Login falhou: {resp.text}")
        token = resp.json().get("access_token", "")

    cfg = _load_config()
    cfg["api_url"] = api_url
    cfg["token"] = token
    _save_config(cfg)
    typer.echo(f"✓ Configurado. Token guardado em {_CONFIG_PATH}")


# ── Env commands ──────────────────────────────────────────────────────────────


@env_app.command("list")
def env_list() -> None:
    """Lista todos os ambientes."""
    with _client() as c:
        resp = c.get("/api/environments")
        if resp.status_code != 200:
            _err(f"Erro: {resp.text}")
    _print_json(resp.json())


@env_app.command("status")
def env_status(slug: str = typer.Argument(..., help="Slug do ambiente")) -> None:
    """Estado do ambiente (running / stopped / none)."""
    with _client() as c:
        resp = c.get(f"/api/environments/{slug}/status")
        if resp.status_code != 200:
            _err(f"Erro: {resp.text}")
    _print_json(resp.json())


@env_app.command("start")
def env_start(slug: str = typer.Argument(..., help="Slug do ambiente")) -> None:
    """Acorda o ambiente (cria container se necessário)."""
    with _client() as c:
        resp = c.post(f"/api/environments/{slug}/wake")
        if resp.status_code not in (200, 202, 204):
            _err(f"Erro: {resp.text}")
    typer.echo(f"✓ Ambiente '{slug}' a iniciar…")


@env_app.command("stop")
def env_stop(slug: str = typer.Argument(..., help="Slug do ambiente")) -> None:
    """Destrói o container do ambiente."""
    confirm = typer.confirm(f"Tem a certeza que quer parar '{slug}'?")
    if not confirm:
        raise typer.Abort()
    with _client() as c:
        resp = c.delete(f"/api/environments/{slug}")
        if resp.status_code not in (200, 204):
            _err(f"Erro: {resp.text}")
    typer.echo(f"✓ Ambiente '{slug}' parado.")


# ── Task commands ─────────────────────────────────────────────────────────────


@task_app.command("list")
def task_list(
    env_slug: Optional[str] = typer.Option(None, "--env", help="Filtrar por env_slug"),
    task_status: Optional[str] = typer.Option(None, "--status", help="Filtrar por status"),
) -> None:
    """Lista tasks de agente."""
    with _client() as c:
        resp = c.get("/api/tasks", params={k: v for k, v in [("env_slug", env_slug), ("status", task_status)] if v})
        if resp.status_code != 200:
            _err(f"Erro: {resp.text}")
    _print_json(resp.json())


@task_app.command("trigger")
def task_trigger(
    env_slug: str = typer.Argument(..., help="Slug do ambiente alvo"),
    prompt: str = typer.Argument(..., help="Instrução para o agente"),
) -> None:
    """Dispara uma nova task de agente via CLI."""
    with _client() as c:
        resp = c.post("/api/tasks", json={"env_slug": env_slug, "prompt": prompt, "triggered_by": "manual"})
        if resp.status_code not in (200, 201):
            _err(f"Erro: {resp.text}")
    data = resp.json()
    typer.echo(f"✓ Task criada: {data.get('task_id')}")


@task_app.command("logs")
def task_logs(
    task_id: str = typer.Argument(..., help="UUID da task"),
    follow: bool = typer.Option(False, "--follow", "-f", help="Seguir eventos em tempo real"),
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
        typer.echo("(--follow: polling a cada 2s, Ctrl+C para sair)")
        import time
        last_id = events[-1]["id"] if events else 0
        while True:
            time.sleep(2)
            with _client() as c2:
                resp2 = c2.get(f"/api/tasks/{task_id}/events", params={"after": last_id})
                if resp2.status_code != 200:
                    break
                new_evs = resp2.json()
                for ev in new_evs:
                    last_id = ev["id"]
                    etype = ev.get("event_type", "")
                    data = ev.get("data", {})
                    msg = data.get("message") or data.get("content") or json.dumps(data)
                    typer.echo(f"[{last_id}] {etype}: {msg}")
                if any(e.get("event_type") in ("done", "error") for e in new_evs):
                    break


# ── Routine commands ──────────────────────────────────────────────────────────


@routine_app.command("list")
def routine_list() -> None:
    """Lista todas as routines."""
    with _client() as c:
        resp = c.get("/api/routines")
        if resp.status_code != 200:
            _err(f"Erro: {resp.text}")
    _print_json(resp.json())


@routine_app.command("create")
def routine_create(
    name: str = typer.Option(..., "--name", help="Nome da routine"),
    env_slug: str = typer.Option(..., "--env", help="Slug do ambiente"),
    prompt: str = typer.Option(..., "--prompt", help="Instrução para o agente"),
    schedule: Optional[str] = typer.Option(None, "--schedule", help="Cron expression (ex: '0 9 * * 1-5')"),
) -> None:
    """Cria uma nova routine."""
    triggers = []
    if schedule:
        triggers.append({"type": "schedule", "config": {"cron": schedule}})
    triggers.append({"type": "api", "config": {}})

    with _client() as c:
        resp = c.post("/api/routines", json={
            "name": name,
            "env_slug": env_slug,
            "prompt": prompt,
            "triggers": triggers,
            "enabled": True,
        })
        if resp.status_code not in (200, 201):
            _err(f"Erro: {resp.text}")
    data = resp.json()
    typer.echo(f"✓ Routine criada: {data.get('id')} — {data.get('name')}")


@routine_app.command("run")
def routine_run(routine_id: str = typer.Argument(..., help="UUID da routine")) -> None:
    """Disparo manual de uma routine."""
    with _client() as c:
        resp = c.post(f"/api/routines/{routine_id}/run")
        if resp.status_code not in (200, 201):
            _err(f"Erro: {resp.text}")
    data = resp.json()
    typer.echo(f"✓ Run disparado: task_id={data.get('task_id')}, run_id={data.get('run_id')}")


@routine_app.command("logs")
def routine_logs(routine_id: str = typer.Argument(..., help="UUID da routine")) -> None:
    """Historial de execuções de uma routine."""
    with _client() as c:
        resp = c.get(f"/api/routines/{routine_id}/runs")
        if resp.status_code != 200:
            _err(f"Erro: {resp.text}")
    _print_json(resp.json())


# ── Webhook test ──────────────────────────────────────────────────────────────


@webhook_app.command("test")
def webhook_test(
    env_slug: str = typer.Option(..., "--env", help="Slug do ambiente"),
    event: str = typer.Option("ci_failed", "--event", help="Tipo de evento simulado"),
) -> None:
    """Simula um evento de webhook para testar o roteamento."""
    test_payloads = {
        "ci_failed": {
            "action": "completed",
            "check_run": {
                "name": "CI / test",
                "conclusion": "failure",
                "head_sha": "abc1234",
                "details_url": "https://github.com/org/repo/actions/runs/1",
                "output": {"summary": "AssertionError in tests/test_main.py:42"},
                "pull_requests": [],
            },
            "repository": {
                "full_name": f"org/{env_slug}",
                "clone_url": f"https://github.com/org/{env_slug}.git",
            },
        },
        "pr_opened": {
            "action": "opened",
            "pull_request": {
                "number": 99,
                "title": "Test PR",
                "body": "Testing the webhook integration.",
            },
            "repository": {
                "full_name": f"org/{env_slug}",
                "clone_url": f"https://github.com/org/{env_slug}.git",
            },
        },
    }

    payload = test_payloads.get(event)
    if not payload:
        _err(f"Evento '{event}' não reconhecido. Use: ci_failed, pr_opened")

    event_header = "check_run" if event == "ci_failed" else "pull_request"

    with _client() as c:
        resp = c.post(
            "/api/webhooks/github",
            json=payload,
            headers={"X-GitHub-Event": event_header},
        )
        if resp.status_code not in (200, 201):
            _err(f"Erro {resp.status_code}: {resp.text}")

    _print_json(resp.json())


if __name__ == "__main__":
    app()
