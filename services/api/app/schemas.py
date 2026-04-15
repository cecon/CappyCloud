"""Esquemas Pydantic para pedidos e respostas HTTP da API.

Validators delegam a app.domain.value_objects (DRY — lógica de validação
definida uma única vez no domínio).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.domain.value_objects import validate_email, validate_password


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


class ConversationCreate(BaseModel):
    """Criação de conversa."""

    title: str | None = Field(default="Nova conversa", max_length=512)


class ConversationOut(BaseModel):
    """Metadados da conversa."""

    id: uuid.UUID
    title: str
    created_at: datetime
    updated_at: datetime

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
