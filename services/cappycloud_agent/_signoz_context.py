"""SigNoz context helpers for the agent pipeline."""

from __future__ import annotations

import logging
import uuid
from contextlib import suppress

import asyncpg

log = logging.getLogger(__name__)


async def fetch_signoz_service_names(
    database_url: str,
    repo_ids: list[str],
) -> dict[str, str]:
    """Retorna {repo_id: signoz_service_name} para os repos que têm o campo preenchido."""
    if not database_url or not repo_ids:
        return {}
    try:
        valid_ids = []
        for rid in repo_ids:
            with suppress(ValueError):
                valid_ids.append(uuid.UUID(rid))
        if not valid_ids:
            return {}
        conn = await asyncpg.connect(database_url)
        try:
            rows = await conn.fetch(
                "SELECT id::text, signoz_service_name FROM repositories "
                "WHERE id = ANY($1) AND signoz_service_name IS NOT NULL",
                valid_ids,
            )
        finally:
            await conn.close()
        return {row["id"]: row["signoz_service_name"] for row in rows}
    except Exception as exc:
        log.warning("[Signoz] falha ao buscar service names: %s", exc)
        return {}


async def has_enabled_signoz_mcp(
    database_url: str,
    sandbox_id: str | None,
) -> bool:
    """Retorna True quando o MCP SignOz está ativo para a sandbox."""
    if not sandbox_id:
        return False
    try:
        sid = uuid.UUID(sandbox_id)
    except ValueError:
        return False
    try:
        conn = await asyncpg.connect(database_url)
        try:
            row = await conn.fetchrow(
                "SELECT 1 FROM mcp_servers "
                "WHERE sandbox_id = $1 AND name = 'signoz' AND enabled = true "
                "LIMIT 1",
                sid,
            )
        finally:
            await conn.close()
        return row is not None
    except Exception as exc:
        log.warning("[Signoz] falha ao verificar MCP ativo: %s", exc)
        return False


def build_signoz_context_section(
    repos: list[dict],
    signoz_names: dict[str, str],
    *,
    mcp_available: bool = True,
) -> str:
    """Monta bloco de contexto SigNoz para injetar no prompt."""
    lines: list[str] = []
    for repo in repos:
        repo_id = str(repo.get("repo_id") or "")
        svc = signoz_names.get(repo_id)
        if svc:
            alias = repo.get("alias") or repo.get("slug") or repo_id[:8]
            lines.append(f"- **{alias}** → `service.name = '{svc}'`")
    if not lines:
        return ""
    if not mcp_available:
        return (
            "## Observabilidade (SigNoz indisponível)\n\n"
            "Os seguintes repositórios têm telemetria configurada no SigNoz, "
            "mas o MCP `signoz` está desativado ou sem credencial funcional neste momento:\n\n"
            + "\n".join(lines)
            + "\n\nNão tente consultar logs, traces ou métricas do SigNoz nesta execução. "
            "Informe ao utilizador que a integração SigNoz está temporariamente indisponível. "
            "Não peça para configurar `service.name`: ele já está mapeado acima para "
            "estes repositórios."
        )
    return (
        "## Observabilidade (SigNoz MCP)\n\n"
        "Os seguintes repositórios têm telemetria configurada no SigNoz. "
        "Ao consultar logs, traces ou métricas, use o `service.name` correspondente:\n\n"
        + "\n".join(lines)
        + "\n\nRegras de consulta:\n"
        "- Use SigNoz somente para repositórios listados acima.\n"
        "- Não peça ao utilizador para configurar `service.name`; ele já está mapeado acima.\n"
        "- Se o utilizador não informar período, consulte por padrão a última hora.\n"
        "- Se a pergunta estiver ampla demais, peça um filtro operacional útil, como CNPJ, "
        "hardware/terminal, loja, endpoint, erro esperado ou janela de tempo específica.\n"
        "- Se houver dados suficientes, consulte primeiro com o `service.name` e período "
        "padrão antes de pedir mais detalhes."
    )
