"""Provider do modelo escolhido: URL, chave e formato que vão para o sandbox."""

import logging
import uuid
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit

import asyncpg

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class LlmProviderRuntimeConfig:
    base_url: str
    api_key: str
    api_format: str


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
        if not path or _path_has_azure_project_openai_v1(path):
            path = "/openai/v1"
    return urlunsplit((parsed.scheme, parsed.netloc, path.rstrip("/"), "", "")), inferred


def _anthropic_runtime_base_url(raw_url: str) -> str:
    """Base da API de mensagens da Anthropic, sem ``/v1/messages``.

    No Azure Foundry a API da Anthropic fica em ``https://<recurso>/anthropic``,
    fora do caminho do projeto que a API estilo OpenAI usa.
    """
    parsed = urlsplit((raw_url or "").strip())
    host = parsed.netloc.split("@")[-1].split(":")[0].lower()
    if host.endswith(".services.ai.azure.com"):
        return urlunsplit((parsed.scheme, parsed.netloc, "/anthropic", "", ""))
    path = parsed.path.rstrip("/")
    for suffix in ("/v1/messages", "/messages", "/v1"):
        if path.lower().endswith(suffix):
            path = path[: -len(suffix)]
            break
    return urlunsplit((parsed.scheme, parsed.netloc, path.rstrip("/"), "", ""))


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


_PROVIDER_FOR_MODEL_SQL = """
    SELECT p.base_url, p.api_key_encrypted, p.api_format, p.name
    FROM ai_models m
    JOIN ai_providers p ON p.id = m.provider_id
    WHERE m.active = TRUE
      AND p.active = TRUE
      AND m.model_id = $1
      AND m.capabilities ? 'text'
"""


def _is_uuid(value: str | None) -> bool:
    if not value:
        return False
    try:
        uuid.UUID(value)
    except ValueError:
        return False
    return True


async def resolve_model_provider_runtime_config(
    database_url: str, model_id: str | None, ai_model_id: str = ""
) -> LlmProviderRuntimeConfig | None:
    """Resolve base URL/chave/formato do provider do modelo selecionado.

    ``ai_model_id`` é a linha do catálogo que a conversa escolheu: o mesmo
    ``model_id`` pode existir em dois providers (ex.: Opus no Azure e no proxy
    do Lynn). Sem ela, ou se ela não bate com ``model_id`` (modelo trocado pelo
    fallback), vale a primeira linha ativa com esse nome, como antes.

    Retorna ``None`` quando o modelo não tem provider configurado com chave; nesse
    caso o sandbox usa as variáveis de ambiente padrão, preservando OpenRouter.
    """
    if not database_url or not model_id:
        return None
    try:
        conn = await asyncpg.connect(database_url)
        try:
            row = None
            if _is_uuid(ai_model_id):
                row = await conn.fetchrow(
                    _PROVIDER_FOR_MODEL_SQL + " AND m.id = $2::uuid LIMIT 1",
                    model_id,
                    ai_model_id,
                )
            if row is None:
                row = await conn.fetchrow(
                    _PROVIDER_FOR_MODEL_SQL + " ORDER BY m.display_name LIMIT 1",
                    model_id,
                )
        finally:
            await conn.close()
        if not row:
            return None
        api_key = _decrypt_secret(str(row["api_key_encrypted"] or ""))
        if not api_key:
            return None
        base_url, inferred_format = _normalise_runtime_base_url(str(row["base_url"] or ""))
        if not base_url:
            return None
        configured_format = str(row["api_format"] or "chat_completions").strip()
        if configured_format == "anthropic":
            # Claude no Azure Foundry só lê imagem pela API da Anthropic; a
            # rota estilo OpenAI aceita a chamada e descarta a imagem.
            return LlmProviderRuntimeConfig(
                base_url=_anthropic_runtime_base_url(str(row["base_url"] or "")),
                api_key=api_key,
                api_format="anthropic",
            )
        api_format = inferred_format or configured_format or "chat_completions"
        if api_format not in {"chat_completions", "responses"}:
            api_format = "chat_completions"
        return LlmProviderRuntimeConfig(
            base_url=base_url,
            api_key=api_key,
            api_format=api_format,
        )
    except Exception as exc:
        log.warning("[Models] falha ao resolver provider do modelo '%s': %s", model_id, exc)
        return None
