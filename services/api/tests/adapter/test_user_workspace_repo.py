from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from typing import Any

import pytest
import pytest_asyncio
from app.adapters.secondary.persistence.sqlalchemy_user_workspace_repo import (
    SQLAlchemyUserRepositoryWorkspaceRepository,
)
from app.domain.entities import UserRepositoryWorkspace
from app.infrastructure.orm_models import Base
from app.infrastructure.orm_models import User as UserORM
from app.infrastructure.orm_models_platform import Repository as RepositoryORM
from app.ports.user_workspaces import UserRepositoryWorkspaceRepository
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from tests.conftest import InMemoryUserWorkspaceRepository


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def sqlite_engine():  # type: ignore[no-untyped-def]
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(sqlite_engine: Any) -> AsyncGenerator[AsyncSession]:
    factory = async_sessionmaker(sqlite_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session


@pytest.fixture(params=["in_memory", "sqlite"])
async def workspace_repo_impl(
    request: pytest.FixtureRequest,
    db_session: AsyncSession,
) -> UserRepositoryWorkspaceRepository:
    if request.param == "in_memory":
        return InMemoryUserWorkspaceRepository()
    return SQLAlchemyUserRepositoryWorkspaceRepository(db_session)


async def _seed_sqlite_fk_rows(
    session: AsyncSession,
    user_id: uuid.UUID,
    repo_id: uuid.UUID,
) -> None:
    session.add(UserORM(id=user_id, email=f"{user_id.hex}@test.com", hashed_password="x"))
    session.add(
        RepositoryORM(
            id=repo_id,
            slug=f"repo-{repo_id.hex[:8]}",
            name="Repo",
            clone_url="https://github.com/acme/repo.git",
            default_branch="main",
        )
    )
    await session.commit()


async def test_save_and_get_for_scope(
    workspace_repo_impl: UserRepositoryWorkspaceRepository,
    db_session: AsyncSession,
) -> None:
    user_id = uuid.uuid4()
    repo_id = uuid.uuid4()
    if isinstance(workspace_repo_impl, SQLAlchemyUserRepositoryWorkspaceRepository):
        await _seed_sqlite_fk_rows(db_session, user_id, repo_id)
    workspace = UserRepositoryWorkspace(
        id=uuid.uuid4(),
        user_id=user_id,
        repository_id=repo_id,
        sandbox_id=None,
        sandbox_key="default",
        base_branch="main",
        workspace_path=f"/repos/users/{user_id.hex[:12]}/default/repo/main",
        status="ready",
    )

    saved = await workspace_repo_impl.save(workspace)
    found = await workspace_repo_impl.get_for_scope(
        user_id=user_id,
        repository_id=repo_id,
        sandbox_key="default",
        base_branch="main",
    )

    assert found is not None
    assert found.id == saved.id
    assert found.workspace_path == workspace.workspace_path


async def test_list_and_delete_are_user_scoped(
    workspace_repo_impl: UserRepositoryWorkspaceRepository,
    db_session: AsyncSession,
) -> None:
    user_id = uuid.uuid4()
    repo_id = uuid.uuid4()
    if isinstance(workspace_repo_impl, SQLAlchemyUserRepositoryWorkspaceRepository):
        await _seed_sqlite_fk_rows(db_session, user_id, repo_id)
    workspace = UserRepositoryWorkspace(
        id=uuid.uuid4(),
        user_id=user_id,
        repository_id=repo_id,
        sandbox_id=None,
        sandbox_key="default",
        base_branch="main",
        workspace_path=f"/repos/users/{user_id.hex[:12]}/default/repo/main",
        status="ready",
    )
    await workspace_repo_impl.save(workspace)

    assert len(await workspace_repo_impl.list_for_user(user_id)) == 1
    assert await workspace_repo_impl.delete(workspace.id, uuid.uuid4()) is False
    assert await workspace_repo_impl.delete(workspace.id, user_id) is True
    assert await workspace_repo_impl.get(workspace.id) is None
