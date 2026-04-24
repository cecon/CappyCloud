"""CLI commands for webhook testing."""

from __future__ import annotations

import typer

webhook_app = typer.Typer(help="Utilitários de webhook.")


def _client():
    from cappy.main import client

    return client()


def _err(msg: str) -> None:
    from cappy.main import err

    err(msg)


def _print(data) -> None:
    from cappy.main import print_json

    print_json(data)


_TEST_PAYLOADS = {
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
    },
    "pr_opened": {
        "action": "opened",
        "pull_request": {
            "number": 99,
            "title": "Test PR",
            "body": "Testing the webhook integration.",
        },
    },
}

_EVENT_HEADERS = {
    "ci_failed": "check_run",
    "pr_opened": "pull_request",
}


@webhook_app.command("test")
def webhook_test(
    env_slug: str = typer.Option(..., "--env", help="Slug do ambiente"),
    event: str = typer.Option("ci_failed", "--event", help="Tipo de evento simulado"),
) -> None:
    """Simula um evento de webhook para testar o roteamento."""
    payload = _TEST_PAYLOADS.get(event)
    if not payload:
        _err(f"Evento '{event}' não reconhecido. Use: ci_failed, pr_opened")

    payload = dict(payload)
    payload["repository"] = {
        "full_name": f"org/{env_slug}",
        "clone_url": f"https://github.com/org/{env_slug}.git",
    }

    event_header = _EVENT_HEADERS.get(event, event)

    with _client() as c:
        resp = c.post(
            "/api/webhooks/github",
            json=payload,
            headers={"X-GitHub-Event": event_header},
        )
        if resp.status_code not in (200, 201):
            _err(f"Erro {resp.status_code}: {resp.text}")

    _print(resp.json())
