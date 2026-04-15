"""Esquemas Pydantic para pedidos e respostas da API."""

from __future__ import annotations

import re
import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

# Alinhado ao frontend (`validation.ts`) — evita rejeições estritas do `EmailStr` / email-validator.
_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]{2,}$")


class UserCreate(BaseModel):
    """Registo de utilizador."""

    email: str = Field(max_length=320)
    password: str = Field(max_length=128)

    @field_validator("email")
    @classmethod
    def email_normalizado(cls, v: object) -> str:
        """Normaliza e valida formato (sem depender de EmailStr)."""
        if v is None:
            raise ValueError("Email é obrigatório.")
        s = str(v).strip().lower()
        if not s:
            raise ValueError("Email é obrigatório.")
        if not _EMAIL_RE.fullmatch(s):
            raise ValueError("Email inválido. Use o formato nome@dominio.com.")
        return s

    @field_validator("password")
    @classmethod
    def password_min_len(cls, v: str) -> str:
        """Garante mensagem clara em português (evita 422 genérico só com metadados)."""
        if len(v) < 8:
            raise ValueError("A password deve ter pelo menos 8 caracteres.")
        return v


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
