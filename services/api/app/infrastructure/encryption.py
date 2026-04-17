"""Fernet symmetric encryption for sensitive DB columns (tokens, API keys).

Usage:
    enc = get_encryptor()
    stored  = enc.encrypt("my-secret-token")   # store this in DB
    plaintext = enc.decrypt(stored)             # retrieve original
"""

from __future__ import annotations

import base64
import os
from functools import lru_cache


class _Encryptor:
    """Thin wrapper around Fernet so the rest of the code stays clean."""

    def __init__(self, key: str) -> None:
        from cryptography.fernet import Fernet

        # Accept raw 32-byte hex or a proper Fernet URL-safe base64 key
        raw = key.strip()
        if len(raw) == 64 and all(c in "0123456789abcdefABCDEF" for c in raw):
            # hex → bytes → url-safe base64 (Fernet key format)
            key_bytes = base64.urlsafe_b64encode(bytes.fromhex(raw))
        elif len(raw) == 44 and raw.endswith("="):
            key_bytes = raw.encode()
        else:
            raise ValueError(
                "ENCRYPTION_KEY must be a 32-byte hex string (64 hex chars) "
                "or a 44-char Fernet key. Generate one with: "
                "python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
            )
        self._f = Fernet(key_bytes)

    def encrypt(self, plaintext: str) -> str:
        """Encrypt a plaintext string; returns URL-safe base64 ciphertext."""
        if not plaintext:
            return ""
        return self._f.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        """Decrypt ciphertext produced by encrypt(); returns original string."""
        if not ciphertext:
            return ""
        return self._f.decrypt(ciphertext.encode()).decode()


@lru_cache(maxsize=1)
def get_encryptor() -> _Encryptor:
    key = os.environ.get("ENCRYPTION_KEY", "")
    if not key:
        # Dev fallback: deterministic key so the server starts without config.
        # NEVER use in production — tokens stored with this key are not secure.
        key = "0" * 64
    return _Encryptor(key)
