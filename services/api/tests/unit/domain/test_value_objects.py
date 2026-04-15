"""Testes unitários para value objects do domínio."""

import pytest
from app.domain.value_objects import validate_email, validate_password


class TestValidateEmail:
    def test_valid_email_normalises_case(self) -> None:
        assert validate_email("User@Example.COM") == "user@example.com"

    def test_valid_email_strips_spaces(self) -> None:
        assert validate_email("  a@b.com  ") == "a@b.com"

    def test_invalid_no_at_sign(self) -> None:
        with pytest.raises(ValueError, match="inválido"):
            validate_email("notanemail")

    def test_invalid_no_domain(self) -> None:
        with pytest.raises(ValueError, match="inválido"):
            validate_email("user@")

    def test_invalid_short_tld(self) -> None:
        with pytest.raises(ValueError, match="inválido"):
            validate_email("user@domain.c")

    def test_empty_string(self) -> None:
        with pytest.raises(ValueError, match="obrigatório"):
            validate_email("")

    def test_whitespace_only(self) -> None:
        with pytest.raises(ValueError, match="obrigatório"):
            validate_email("   ")

    def test_valid_subdomain(self) -> None:
        assert validate_email("user@mail.example.com") == "user@mail.example.com"


class TestValidatePassword:
    def test_valid_password_returned_unchanged(self) -> None:
        assert validate_password("pass1234") == "pass1234"

    def test_too_short(self) -> None:
        with pytest.raises(ValueError, match="8 caracteres"):
            validate_password("short")

    def test_exactly_min_length(self) -> None:
        assert validate_password("12345678") == "12345678"

    def test_long_password_accepted(self) -> None:
        pw = "a" * 128
        assert validate_password(pw) == pw
