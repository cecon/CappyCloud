"""CLI CappyCloud — entry point e comandos de ambiente."""

from __future__ import annotations

import json
import os
from pathlib import Path

import httpx
import typer

from cappy._task_cmds import task_app
from cappy._routine_cmds import routine_app
from cappy._webhook_cmds import webhook_app

app = typer.Typer(
    name="cappy",
    help="CappyCloud CLI — gere ambientes, tasks e routines.",
    no_args_is_help=True,
)
env_app = typer.Typer(help="Gestão de ambientes Docker.")

app.add_typer(env_app, name="env")
app.add_typer(task_app, name="task")
app.add_typer(routine_app, name="routine")
app.add_typer(webhook_app, name="webhook")

_CONFIG_PATH = Path.home() / ".cappy" / "config.json"


def load_config() -> dict:
    if _CONFIG_PATH.exists():
        return json.loads(_CONFIG_PATH.read_text())
    return {}


def get_api_url() -> str:
    return os.getenv("CAPPY_API_URL") or load_config().get("api_url") or "http://localhost:8000"


def get_token() -> str:
    return os.getenv("CAPPY_TOKEN") or load_config().get("token") or ""


def client() -> httpx.Client:
    token = get_token()
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return httpx.Client(base_url=get_api_url(), headers=headers, timeout=30)


def print_json(data) -> None:
    typer.echo(json.dumps(data, indent=2, ensure_ascii=False, default=str))


def err(msg: str) -> None:
    typer.echo(f"[erro] {msg}", err=True)
    raise typer.Exit(1)


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
            err(f"Login falhou: {resp.text}")
        token = resp.json().get("access_token", "")

    cfg = load_config()
    cfg["api_url"] = api_url
    cfg["token"] = token
    _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    _CONFIG_PATH.write_text(json.dumps(cfg, indent=2))
    typer.echo(f"✓ Configurado. Token guardado em {_CONFIG_PATH}")


@env_app.command("list")
def env_list() -> None:
    """Lista todos os ambientes."""
    with client() as c:
        resp = c.get("/api/environments")
        if resp.status_code != 200:
            err(f"Erro: {resp.text}")
    print_json(resp.json())


@env_app.command("status")
def env_status(slug: str = typer.Argument(..., help="Slug do ambiente")) -> None:
    """Estado do ambiente."""
    with client() as c:
        resp = c.get(f"/api/environments/{slug}/status")
        if resp.status_code != 200:
            err(f"Erro: {resp.text}")
    print_json(resp.json())


@env_app.command("start")
def env_start(slug: str = typer.Argument(..., help="Slug do ambiente")) -> None:
    """Acorda o ambiente."""
    with client() as c:
        resp = c.post(f"/api/environments/{slug}/wake")
        if resp.status_code not in (200, 202, 204):
            err(f"Erro: {resp.text}")
    typer.echo(f"✓ Ambiente '{slug}' a iniciar…")


@env_app.command("stop")
def env_stop(slug: str = typer.Argument(..., help="Slug do ambiente")) -> None:
    """Destrói o container do ambiente."""
    if not typer.confirm(f"Tem a certeza que quer parar '{slug}'?"):
        raise typer.Abort()
    with client() as c:
        resp = c.delete(f"/api/environments/{slug}")
        if resp.status_code not in (200, 204):
            err(f"Erro: {resp.text}")
    typer.echo(f"✓ Ambiente '{slug}' parado.")


if __name__ == "__main__":
    app()
