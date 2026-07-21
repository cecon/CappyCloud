"""Contract tests for ModelProfileLookupPort implementations."""

import uuid

from app.domain.entities import UserRole
from app.ports.model_profiles import AuthorizedModelProfile

from tests.fakes_chat_commands import FakeModelProfileLookup


async def test_model_profile_port_returns_visible_profiles() -> None:
    lookup = FakeModelProfileLookup(
        [
            AuthorizedModelProfile(
                model_id="openrouter/free",
                display_name="Free",
                provider="OpenRouter",
                active=True,
                provider_active=True,
                capabilities=["text"],
                context_window=128000,
            ),
            AuthorizedModelProfile(
                model_id="provider/inactive",
                display_name="Inactive",
                provider="Provider",
                active=False,
                provider_active=False,
                capabilities=["text"],
                context_window=32000,
                unavailable_reason="Provider inativo.",
            ),
        ]
    )

    profiles = await lookup.list_for_user(uuid.uuid4(), UserRole.USER)

    assert [profile.model_id for profile in profiles] == ["openrouter/free", "provider/inactive"]
    assert profiles[1].unavailable_reason == "Provider inativo."

