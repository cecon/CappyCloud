"""Unit tests for Fernet encryption utility."""

from __future__ import annotations

import pytest
from app.infrastructure.encryption import _Encryptor, get_encryptor


class TestEncryptor:
    @pytest.fixture
    def enc(self) -> _Encryptor:
        # Valid 32-byte hex key (dev default)
        return _Encryptor("0" * 64)

    def test_encrypt_decrypt_roundtrip(self, enc: _Encryptor) -> None:
        plaintext = "my-secret-token"
        ciphertext = enc.encrypt(plaintext)
        assert ciphertext != plaintext
        assert enc.decrypt(ciphertext) == plaintext

    def test_encrypt_empty_returns_empty(self, enc: _Encryptor) -> None:
        assert enc.encrypt("") == ""

    def test_decrypt_empty_returns_empty(self, enc: _Encryptor) -> None:
        assert enc.decrypt("") == ""

    def test_fernet_base64_key_accepted(self) -> None:
        from cryptography.fernet import Fernet

        key = Fernet.generate_key().decode()
        enc = _Encryptor(key)
        assert enc.decrypt(enc.encrypt("hello")) == "hello"

    def test_invalid_key_raises(self) -> None:
        with pytest.raises(ValueError, match="ENCRYPTION_KEY"):
            _Encryptor("not-a-valid-key")

    def test_get_encryptor_returns_singleton(self) -> None:
        enc1 = get_encryptor()
        enc2 = get_encryptor()
        assert enc1 is enc2
