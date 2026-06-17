import uuid

import pytest
from app.application.use_cases.agentic_delivery_review import ManageSensitiveSurfaces
from app.domain.agentic_delivery import AgenticPermissionValue
from app.domain.entities import User, UserRole

from tests.fakes_agentic_delivery import FakeAgenticDeliveryRepository


@pytest.mark.asyncio
async def test_sensitive_surface_requires_permission_for_non_admin() -> None:
    repo = FakeAgenticDeliveryRepository()
    user = User(id=uuid.uuid4(), email="u@example.com", hashed_password="x", role=UserRole.USER)
    surface = {
        "repository_id": uuid.uuid4(),
        "domain_key": "erp-a",
        "name": "Fiscal",
        "description": "",
        "match_rules": {"keywords": ["NFCe"]},
        "active": True,
    }

    with pytest.raises(PermissionError):
        await ManageSensitiveSurfaces(repo).save(uuid.uuid4(), surface, user)

    await repo.upsert_permission(
        uuid.uuid4(),
        user.id,
        uuid.uuid4(),
        AgenticPermissionValue.MANAGE_SENSITIVE_SURFACES,
        True,
        repository_id=surface["repository_id"],
        domain_key="erp-a",
    )

    saved = await ManageSensitiveSurfaces(repo).save(uuid.uuid4(), surface, user)
    assert saved["name"] == "Fiscal"
