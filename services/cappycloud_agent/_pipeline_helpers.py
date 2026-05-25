import json
import logging
import os
import uuid
from contextlib import suppress
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit

import asyncpg
import httpx

from ._agent_context import (
    fetch_worktree_top_levels,
    inject_section_before_user_message,
    render_worktree_top_level_section,
)

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class LlmProviderRuntimeConfig:
    base_url: str
    api_key: str
    api_format: str


def db_url() -> str:
    explicit = os.getenv("PIPELINE_DATABASE_URL", "").strip()
    raw = explicit or os.getenv("DATABASE_URL", "")
    return raw.replace("postgresql+asyncpg://", "postgresql://", 1)


def sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def inject_repo_context(user_message: str, repos: list, session_root: str) -> str:
    """Injeta comandos /add para cada worktree antes da mensagem do utilizador.

    Apenas relevante em sessões **multi-repo** (>1 repo): cada repo recebe um
    ``/add <path>`` para o openclaude conseguir navegar entre os repositórios.
    """
    if not repos or not session_root:
        return user_message
    if len(repos) <= 1:
        return user_message

    add_lines: list[str] = []
    for repo in repos:
        alias = repo.get("alias") or repo.get("slug", "")
        if not alias:
            continue
        wt_path = repo.get("worktree_path") or f"{session_root}/{alias}"
        add_lines.append(f"/add {wt_path}")
        log.debug("Injecting /add %s", wt_path)

    if not add_lines:
        return user_message

    return "\n".join(add_lines) + "\n\n" + user_message


async def build_prompt_with_worktree_context(
    prompt: str,
    sandbox_session_url: str,
    repos: list[dict],
    session_root: str | None,
) -> str:
    """Injeta snapshot do worktree no prompt. Degrada graciosamente em caso de erro."""
    if not repos:
        return prompt
    try:
        top_level = await fetch_worktree_top_levels(
            sandbox_session_url, repos, session_root or ""
        )
        section = render_worktree_top_level_section(top_level)
        if section:
            return inject_section_before_user_message(prompt, section)
    except Exception as exc:
        log.warning("[Dispatcher] worktree top-level fetch falhou: %s", exc)
    return prompt


async def push_mcp_config(
    database_url: str,
    sandbox_id: str,
    sandbox_session_url: str,
) -> None:
    """Busca MCPs ativos da sandbox no DB e envia ao sandbox via POST /mcp/configure.

    Degrada graciosamente: qualquer erro é logado como warning sem interromper o dispatch.
    """
    if not sandbox_id or not sandbox_session_url or not database_url:
        return
    try:
        sid = uuid.UUID(sandbox_id)
    except ValueError:
        return
    try:
        conn = await asyncpg.connect(database_url)
        try:
            rows = await conn.fetch(
                "SELECT name, command, args, env FROM mcp_servers "
                "WHERE sandbox_id = $1 AND enabled = true",
                sid,
            )
        finally:
            await conn.close()

        mcp_servers: dict = {}
        for row in rows:
            entry: dict = {"command": row["command"]}
            if row["args"]:
                args_val = row["args"]
                if isinstance(args_val, str):
                    args_val = json.loads(args_val)
                entry["args"] = list(args_val)
            if row["env"]:
                env_val = row["env"]
                if isinstance(env_val, str):
                    env_val = json.loads(env_val)
                entry["env"] = env_val if isinstance(env_val, dict) else dict(env_val)
            mcp_servers[row["name"]] = entry

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{sandbox_session_url}/mcp/configure",
                json={"mcpServers": mcp_servers},
            )
        log.info(
            "[MCP] config enviada ao sandbox: %d servidores → %s",
            len(mcp_servers),
            resp.status_code,
        )
    except Exception as exc:
        log.warning("[MCP] falha ao enviar config ao sandbox: %s", exc)


async def fetch_signoz_service_names(
    database_url: str,
    repo_ids: list[str],
) -> dict[str, str]:
    """Retorna {repo_id: signoz_service_name} para os repos que têm o campo preenchido.

    Degrada graciosamente: retorna dict vazio em caso de erro.
    """
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


async def fetch_default_text_model_id(database_url: str) -> str | None:
    """Busca o modelo texto default ativo no catálogo do banco."""
    if not database_url:
        return None
    try:
        conn = await asyncpg.connect(database_url)
        try:
            row = await conn.fetchrow(
                """
                SELECT m.model_id
                FROM ai_models m
                JOIN ai_providers p ON p.id = m.provider_id
                WHERE m.active = TRUE
                  AND p.active = TRUE
                  AND COALESCE((m.is_default->>'text')::boolean, FALSE) = TRUE
                  AND m.capabilities ? 'text'
                ORDER BY m.display_name
                LIMIT 1
                """
            )
            if row:
                return str(row["model_id"])
            row = await conn.fetchrow(
                """
                SELECT m.model_id
                FROM ai_models m
                JOIN ai_providers p ON p.id = m.provider_id
                WHERE m.active = TRUE
                  AND p.active = TRUE
                  AND m.capabilities ? 'text'
                ORDER BY m.display_name
                LIMIT 1
                """
            )
            return str(row["model_id"]) if row else None
        finally:
            await conn.close()
    except Exception as exc:
        log.warning("[Models] falha ao buscar modelo default: %s", exc)
        return None


async def resolve_text_model_id(
    database_url: str, requested_model: str | None
) -> str | None:
    """Mantém o modelo pedido se ele estiver ativo e suportar texto."""
    if database_url and requested_model:
        try:
            conn = await asyncpg.connect(database_url)
            try:
                row = await conn.fetchrow(
                    """
                    SELECT 1
                    FROM ai_models m
                    JOIN ai_providers p ON p.id = m.provider_id
                    WHERE m.active = TRUE
                      AND p.active = TRUE
                      AND m.model_id = $1
                      AND m.capabilities ? 'text'
                    LIMIT 1
                    """,
                    requested_model,
                )
                if row:
                    return requested_model
            finally:
                await conn.close()
        except Exception as exc:
            log.warning("[Models] falha ao validar modelo pedido: %s", exc)
    return await fetch_default_text_model_id(database_url)


resolve_free_text_model_id = resolve_text_model_id


def _decrypt_secret(ciphertext: str) -> str:
    if not ciphertext:
        return ""
    try:
        from app.infrastructure.encryption import get_encryptor

        return get_encryptor().decrypt(ciphertext)
    except Exception as exc:
        log.warning("[Models] falha ao decriptar chave do provider: %s", exc)
        return ""


def _normalise_runtime_base_url(raw_url: str) -> tuple[str, str | None]:
    raw = (raw_url or "").strip()
    if not raw:
        return "", None
    parsed = urlsplit(raw)
    path = parsed.path.rstrip("/")
    lower_path = path.lower()
    inferred: str | None = None
    if lower_path.endswith("/responses"):
        path = path[: -len("/responses")]
        inferred = "responses"
    elif lower_path.endswith("/chat/completions"):
        path = path[: -len("/chat/completions")]
        inferred = "chat_completions"
    host = parsed.netloc.split("@")[-1].split(":")[0].lower()
    if host.endswith(".services.ai.azure.com"):
        if not path:
            path = "/openai/v1"
        elif _path_has_azure_project_openai_v1(path):
            path = "/openai/v1"
    return urlunsplit(
        (parsed.scheme, parsed.netloc, path.rstrip("/"), "", "")
    ), inferred


def _path_has_azure_project_openai_v1(path: str) -> bool:
    parts = [part.lower() for part in path.strip("/").split("/") if part]
    return (
        len(parts) >= 5
        and parts[:2] == ["api", "projects"]
        and parts[-2:]
        == [
            "openai",
            "v1",
        ]
    )


async def resolve_model_provider_runtime_config(
    database_url: str, model_id: str | None
) -> LlmProviderRuntimeConfig | None:
    """Resolve base URL/chave/formato do provider do modelo selecionado.

    Retorna ``None`` quando o modelo não tem provider configurado com chave; nesse
    caso o sandbox usa as variáveis de ambiente padrão, preservando OpenRouter.
    """
    if not database_url or not model_id:
        return None
    try:
        conn = await asyncpg.connect(database_url)
        try:
            row = await conn.fetchrow(
                """
                SELECT p.base_url, p.api_key_encrypted, p.api_format, p.name
                FROM ai_models m
                JOIN ai_providers p ON p.id = m.provider_id
                WHERE m.active = TRUE
                  AND p.active = TRUE
                  AND m.model_id = $1
                  AND m.capabilities ? 'text'
                ORDER BY m.display_name
                LIMIT 1
                """,
                model_id,
            )
        finally:
            await conn.close()
        if not row:
            return None
        api_key = _decrypt_secret(str(row["api_key_encrypted"] or ""))
        if not api_key:
            return None
        base_url, inferred_format = _normalise_runtime_base_url(
            str(row["base_url"] or "")
        )
        if not base_url:
            return None
        configured_format = str(row["api_format"] or "chat_completions").strip()
        api_format = inferred_format or configured_format or "chat_completions"
        if api_format not in {"chat_completions", "responses"}:
            api_format = "chat_completions"
        return LlmProviderRuntimeConfig(
            base_url=base_url,
            api_key=api_key,
            api_format=api_format,
        )
    except Exception as exc:
        log.warning(
            "[Models] falha ao resolver provider do modelo '%s': %s", model_id, exc
        )
        return None


def build_signoz_context_section(
    repos: list[dict],
    signoz_names: dict[str, str],
    *,
    mcp_available: bool = True,
) -> str:
    """Monta bloco de contexto SigNoz para injetar no prompt.

    Retorna string vazia se nenhum repo da sessão tiver service_name configurado.
    """
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
