"""Testes unitários para value objects do domínio."""

import pytest
from app.domain.value_objects import (
    DEFAULT_EXECUTION_PROFILE,
    DEFAULT_PERMISSION_MODE,
    ExecutionProfile,
    PermissionMode,
    validate_email,
    validate_execution_profile,
    validate_password,
    validate_permission_mode,
)


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


class TestValidatePermissionMode:
    def test_default_permission_mode_is_bypass_permissions(self) -> None:
        assert PermissionMode.BYPASS_PERMISSIONS.value == DEFAULT_PERMISSION_MODE

    @pytest.mark.parametrize("mode", [mode.value for mode in PermissionMode])
    def test_accepts_supported_permission_modes(self, mode: str) -> None:
        assert validate_permission_mode(mode) == mode

    def test_omitted_permission_mode_uses_default(self) -> None:
        assert validate_permission_mode(None) == PermissionMode.BYPASS_PERMISSIONS.value

    def test_rejects_unknown_permission_mode(self) -> None:
        with pytest.raises(ValueError, match="modo de permissão"):
            validate_permission_mode("dangerously_free")


class TestValidateExecutionProfile:
    def test_default_execution_profile_is_medium(self) -> None:
        assert ExecutionProfile.MEDIUM.value == DEFAULT_EXECUTION_PROFILE

    @pytest.mark.parametrize("profile", [profile.value for profile in ExecutionProfile])
    def test_accepts_supported_execution_profiles(self, profile: str) -> None:
        assert validate_execution_profile(profile) == profile

    def test_omitted_execution_profile_uses_default(self) -> None:
        assert validate_execution_profile(None) == ExecutionProfile.MEDIUM.value

    def test_rejects_unknown_execution_profile(self) -> None:
        with pytest.raises(ValueError, match="perfil de execucao"):
            validate_execution_profile("turbo")
