"""Derive administrator-visible AI provider authentication state."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class ProviderAuthSubject(Protocol):
    name: str
    active: bool
    api_key_encrypted: str


@dataclass(frozen=True)
class ProviderAuthState:
    state: str
    label: str
    next_action: str


class DeriveProviderAuthState:
    """Classify provider auth without exposing or decrypting credentials."""

    def execute(self, provider: ProviderAuthSubject) -> ProviderAuthState:
        if not provider.active:
            return ProviderAuthState(
                state="inactive",
                label="Provider inativo",
                next_action="Ative o provider antes de sincronizar ou usar modelos.",
            )
        if str(provider.api_key_encrypted or "").strip():
            return ProviderAuthState(
                state="configured",
                label="Chave configurada",
                next_action="Sincronize o catálogo ou valide um modelo no chat.",
            )
        if provider.name.strip().lower() == "openrouter":
            return ProviderAuthState(
                state="catalog-only",
                label="Catálogo público",
                next_action="Cadastre uma chave se o runtime precisar executar modelos pagos.",
            )
        return ProviderAuthState(
            state="missing-key",
            label="Chave pendente",
            next_action="Cadastre a chave do provider para liberar execução no runtime.",
        )
