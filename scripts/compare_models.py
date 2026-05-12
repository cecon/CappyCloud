"""Compara a mesma pergunta executada por modelos diferentes via CappyCloud.

Cria N conversas (uma por modelo), envia o mesmo prompt em cada e aguarda a
conclusão. No fim, gera um relatório markdown com:

- métricas de cada execução (tokens, custo, duração, nº de tool calls)
- diff visual lado-a-lado das respostas finais
- nº de eventos por tipo (text, tool_start, tool_result, action_required)

Uso:
    # Variáveis obrigatórias
    $env:CAPPY_API_BASE  = "http://localhost:38000"
    $env:CAPPY_API_TOKEN = "<bearer token do utilizador>"
    $env:CAPPY_REPO_ID   = "<uuid do repositório a associar>"
    $env:CAPPY_DATABASE_URL = "postgresql://user:pass@localhost:15432/cappycloud"

    # Lista de modelos (separados por vírgula). Ex.:
    $env:CAPPY_MODELS = "anthropic/claude-3.5-sonnet,openai/gpt-4o,deepseek/deepseek-chat"

    python scripts/compare_models.py "olhe no /repos/autosystem e mapeie o impacto da NT 2025.001"

Saída: scripts/comparison_<timestamp>.md
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import asyncpg
import httpx


def env(name: str, default: str | None = None) -> str:
    val = os.getenv(name, default)
    if not val:
        raise SystemExit(f"Variável de ambiente {name} é obrigatória.")
    return val


async def create_conversation(
    client: httpx.AsyncClient, base: str, token: str, repo_id: str, title: str
) -> str:
    """Cria uma conversa nova e devolve o conversation_id."""
    resp = await client.post(
        f"{base}/api/conversations",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": title, "repository_id": repo_id},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["id"]


async def send_message_streaming(
    client: httpx.AsyncClient,
    base: str,
    token: str,
    conversation_id: str,
    content: str,
    model_id: str,
) -> None:
    """Dispara a mensagem em SSE e drena até receber 'done' ou 'error'."""
    async with client.stream(
        "POST",
        f"{base}/api/conversations/{conversation_id}/messages/stream",
        headers={"Authorization": f"Bearer {token}", "Accept": "text/event-stream"},
        json={"content": content, "model_id": model_id},
        timeout=None,
    ) as resp:
        resp.raise_for_status()
        async for line in resp.aiter_lines():
            if not line:
                continue
            if line.startswith("data:"):
                payload = line[5:].strip()
                if not payload:
                    continue
                try:
                    evt = json.loads(payload)
                except json.JSONDecodeError:
                    continue
                if evt.get("type") in ("done", "error"):
                    return


async def collect_metrics(
    pool: asyncpg.Pool, conversation_id: str
) -> dict[str, Any]:
    """Lê agent_tasks + agent_events para a conversa e produz métricas."""
    async with pool.acquire() as conn:
        task = await conn.fetchrow(
            """
            SELECT id, status, model_used, prompt_tokens, completion_tokens,
                   cost_usd, started_at, completed_at
            FROM agent_tasks
            WHERE conversation_id = $1::uuid
            ORDER BY created_at DESC
            LIMIT 1
            """,
            conversation_id,
        )
        if not task:
            return {"error": "task não encontrada"}

        events = await conn.fetch(
            """
            SELECT event_type, data
            FROM agent_events
            WHERE task_id = $1::uuid
            ORDER BY id
            """,
            task["id"],
        )

    counts: dict[str, int] = {}
    final_text_chunks: list[str] = []
    tool_names: list[str] = []
    for evt in events:
        et = evt["event_type"]
        counts[et] = counts.get(et, 0) + 1
        try:
            data = json.loads(evt["data"]) if isinstance(evt["data"], str) else evt["data"]
        except (TypeError, json.JSONDecodeError):
            data = {}
        if et == "text" and isinstance(data, dict):
            final_text_chunks.append(str(data.get("content", "")))
        if et == "tool_start" and isinstance(data, dict):
            tool_names.append(str(data.get("name", "?")))

    duration_s = None
    if task["started_at"] and task["completed_at"]:
        duration_s = (task["completed_at"] - task["started_at"]).total_seconds()

    return {
        "task_id": str(task["id"]),
        "status": task["status"],
        "model_used": task["model_used"],
        "prompt_tokens": int(task["prompt_tokens"] or 0),
        "completion_tokens": int(task["completion_tokens"] or 0),
        "cost_usd": float(task["cost_usd"] or 0),
        "duration_s": duration_s,
        "event_counts": counts,
        "n_tool_calls": counts.get("tool_start", 0),
        "tool_names_unique": sorted(set(tool_names)),
        "final_text": "".join(final_text_chunks),
    }


async def run_one(
    client: httpx.AsyncClient,
    pool: asyncpg.Pool,
    base: str,
    token: str,
    repo_id: str,
    prompt: str,
    model_id: str,
) -> dict[str, Any]:
    """Cria conversa, envia mensagem, espera completar, devolve métricas."""
    label = model_id.replace("/", "_")
    title = f"[CMP] {label} - {datetime.now(timezone.utc):%H:%M:%S}"
    print(f"[{model_id}] criando conversa…", flush=True)
    conv_id = await create_conversation(client, base, token, repo_id, title)
    print(f"[{model_id}] conversa = {conv_id}", flush=True)

    t0 = time.time()
    try:
        await send_message_streaming(client, base, token, conv_id, prompt, model_id)
    except Exception as exc:  # noqa: BLE001
        print(f"[{model_id}] erro no stream: {exc}", flush=True)

    print(
        f"[{model_id}] stream terminou em {time.time() - t0:.1f}s — coletando métricas",
        flush=True,
    )
    metrics = await collect_metrics(pool, conv_id)
    metrics["conversation_id"] = conv_id
    metrics["wall_time_s"] = round(time.time() - t0, 1)
    return metrics


def render_report(prompt: str, results: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines.append(f"# Comparativo de modelos — {ts}\n")
    lines.append(f"**Prompt:**\n\n> {prompt}\n")
    lines.append("## Métricas\n")
    lines.append(
        "| Modelo | Status | Wall (s) | LLM (s) | Tool calls | Tools usadas |"
        " Prompt tok | Compl tok | Custo (USD) |"
    )
    lines.append("|---|---|---:|---:|---:|---|---:|---:|---:|")
    for r in results:
        tools = ", ".join(r.get("tool_names_unique") or []) or "-"
        lines.append(
            "| `{model}` | {status} | {wall} | {dur} | {tc} | {tools} | "
            "{pt} | {ct} | {cost:.4f} |".format(
                model=r.get("model_used") or "?",
                status=r.get("status") or "?",
                wall=r.get("wall_time_s") or "?",
                dur=r.get("duration_s") or "?",
                tc=r.get("n_tool_calls") or 0,
                tools=tools,
                pt=r.get("prompt_tokens") or 0,
                ct=r.get("completion_tokens") or 0,
                cost=r.get("cost_usd") or 0,
            )
        )

    lines.append("\n## Eventos por tipo\n")
    lines.append("| Modelo | text | tool_start | tool_result | action_req | error |")
    lines.append("|---|---:|---:|---:|---:|---:|")
    for r in results:
        c = r.get("event_counts") or {}
        lines.append(
            f"| `{r.get('model_used') or '?'}` | {c.get('text', 0)} | "
            f"{c.get('tool_start', 0)} | {c.get('tool_result', 0)} | "
            f"{c.get('action_required', 0)} | {c.get('error', 0)} |"
        )

    lines.append("\n## Resposta final (preview - primeiros 800 chars)\n")
    for r in results:
        text = (r.get("final_text") or "").strip()
        preview = text[:800] + ("…" if len(text) > 800 else "")
        lines.append(f"### `{r.get('model_used') or '?'}`\n")
        lines.append(f"> conversa: `{r.get('conversation_id')}`\n")
        lines.append("```\n" + preview + "\n```\n")

    return "\n".join(lines)


async def amain(prompt: str, models: list[str]) -> None:
    base = env("CAPPY_API_BASE").rstrip("/")
    token = env("CAPPY_API_TOKEN")
    repo_id = env("CAPPY_REPO_ID")
    db_url = env("CAPPY_DATABASE_URL")

    pool = await asyncpg.create_pool(db_url, min_size=1, max_size=4)
    try:
        async with httpx.AsyncClient() as client:
            tasks = [
                run_one(client, pool, base, token, repo_id, prompt, m)
                for m in models
            ]
            results = await asyncio.gather(*tasks, return_exceptions=False)
    finally:
        await pool.close()

    out = Path(__file__).parent / f"comparison_{int(time.time())}.md"
    out.write_text(render_report(prompt, results), encoding="utf-8")
    print(f"\nRelatório: {out}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prompt", help="Mensagem a enviar para todos os modelos")
    parser.add_argument(
        "--models",
        default=os.getenv(
            "CAPPY_MODELS",
            "anthropic/claude-3.5-sonnet,openai/gpt-4o,deepseek/deepseek-chat",
        ),
        help="Lista de modelos separados por vírgula (ou via CAPPY_MODELS env).",
    )
    args = parser.parse_args()
    models = [m.strip() for m in args.models.split(",") if m.strip()]
    if not models:
        print("Nenhum modelo informado.", file=sys.stderr)
        sys.exit(2)
    asyncio.run(amain(args.prompt, models))


if __name__ == "__main__":
    main()
