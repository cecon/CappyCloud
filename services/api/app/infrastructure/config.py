"""Configuração da API (variáveis de ambiente)."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Definições carregadas de `.env` / ambiente."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "CappyCloud API"
    debug: bool = False

    database_url: str = "postgresql+asyncpg://cappy:cappypass@localhost:5432/cappycloud"
    jwt_secret: str = "change-me"  # env: JWT_SECRET
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24

    cors_origins: str = "http://localhost:5173,http://localhost:38081"

    # Chave Fernet para tokens no banco (32-byte hex ou Fernet base64).
    # Gerar: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key())"
    encryption_key: str = "0" * 64  # sobrescrever em produção via ENCRYPTION_KEY

    # Webhook secrets (ainda usados para validar assinaturas)
    github_webhook_secret: str = ""
    gitlab_webhook_secret: str = ""

    # Storage local de anexos (volume Docker dentro do container da API).
    # Cada conversa ganha o seu subdiretório; nomes aleatórios (uuid+ext).
    attachments_dir: str = "/var/cappycloud/attachments"
    attachments_max_bytes: int = 8 * 1024 * 1024  # 8 MB por anexo

    # Vision describer (Caminho C - V1): pré-processa imagens via modelo
    # multimodal e injeta descrição textual no prompt. Permite que modelos
    # text-only no agente raciocinem sobre imagens anexadas.
    vision_provider_base_url: str = "https://openrouter.ai/api/v1"
    vision_provider_api_key: str = ""  # env: VISION_PROVIDER_API_KEY
    vision_model: str = "openai/gpt-4o-mini"
    vision_max_tokens: int = 800
    vision_timeout_s: int = 60


@lru_cache
def get_settings() -> Settings:
    """Retorna instância única de configuração."""
    return Settings()


def cors_origins_list() -> list[str]:
    """Lista de origens CORS a partir de string separada por vírgulas."""
    return [o.strip() for o in get_settings().cors_origins.split(",") if o.strip()]
