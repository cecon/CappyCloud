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

    # GitHub integration
    github_token: str = ""
    github_webhook_secret: str = ""

    # GitLab integration
    gitlab_webhook_secret: str = ""


@lru_cache
def get_settings() -> Settings:
    """Retorna instância única de configuração."""
    return Settings()


def cors_origins_list() -> list[str]:
    """Lista de origens CORS a partir de string separada por vírgulas."""
    return [o.strip() for o in get_settings().cors_origins.split(",") if o.strip()]
