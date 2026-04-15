"""Esquemas Pydantic para pedidos e respostas HTTP da API.

Validators delegam a app.domain.value_objects (DRY — lógica de validação
definida uma única vez no domínio).
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.domain.value_objects import validate_email, validate_password

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9\-]{1,62}[a-z0-9]$")


class UserCreate(BaseModel):
    """Registo de utilizador."""

    email: str = Field(max_length=320)
    password: str = Field(max_length=128)

    @field_validator("email")
    @classmethod
    def email_normalizado(cls, v: object) -> str:
        return validate_email(str(v))

    @field_validator("password")
    @classmethod
    def password_min_len(cls, v: str) -> str:
        return validate_password(v)


class UserOut(BaseModel):
    """Dados públicos do utilizador."""

    id: uuid.UUID
    email: str

    model_config = {"from_attributes": True}


class Token(BaseModel):
    """Resposta OAuth2 com JWT."""

    access_token: str
    token_type: str = "bearer"


class RepoEnvCreate(BaseModel):
    """Criação de ambiente de repositório global."""

    slug: str = Field(
        min_length=3,
        max_length=64,
        description="Identificador curto: minúsculas, números e hífens. Ex.: meu-projeto",
    )
    name: str = Field(min_length=1, max_length=256)
    repo_url: str = Field(min_length=1, max_length=2048)
    branch: str = Field(default="main", min_length=1, max_length=256)

    @field_validator("slug")
    @classmethod
    def slug_valido(cls, v: str) -> str:
        if not _SLUG_RE.match(v):
            raise ValueError(
                "Slug inválido. Use apenas minúsculas, números e hífens "
                "(ex.: meu-projeto). Deve começar e terminar em letra/número."
            )
        return v


class RepoEnvOut(BaseModel):
    """Dados públicos de um ambiente de repositório."""

    id: uuid.UUID
    slug: str
    name: str
    repo_url: str
    branch: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationCreate(BaseModel):
    """Criação de conversa."""

    title: str | None = Field(default="Nova conversa", max_length=512)
    environment_id: uuid.UUID | None = None
    base_branch: str | None = Field(default=None, max_length=255)


class ConversationOut(BaseModel):
    """Metadados da conversa."""

    id: uuid.UUID
    title: str
    created_at: datetime
    updated_at: datetime
    environment_id: uuid.UUID | None = None
    env_slug: str | None = None
    base_branch: str | None = None

    model_config = {"from_attributes": True}


class MessageOut(BaseModel):
    """Mensagem persistida."""

    id: uuid.UUID
    role: str
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


class SendMessageBody(BaseModel):
    """Corpo para enviar mensagem ao agente."""

    content: str = Field(min_length=1, max_length=1_000_000)
